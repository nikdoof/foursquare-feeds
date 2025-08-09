#!/usr/bin/env python3
import argparse
import configparser
import logging
import os
from datetime import timedelta
from xml.sax.saxutils import escape as xml_escape

import arrow
import caldav
import foursquare
from dateutil.tz import tzoffset
from ics import Calendar, Event

current_dir = os.path.realpath(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(current_dir, "config.ini")

# The kinds of file we can generate:
VALID_KINDS = ["ics", "kml", "caldav"]


class FeedGenerator:
    fetch = "recent"

    def __init__(self, fetch="recent"):
        "Loads config, sets up Foursquare API client."

        self.fetch = fetch
        self.logger = logging.getLogger(self.__class__.__name__)

        self._load_config(CONFIG_FILE)

        self.client = foursquare.Foursquare(access_token=self.api_access_token)

    def _load_config(self, config_file):
        "Set object variables based on supplied config file."
        config = configparser.ConfigParser()

        try:
            config.read_file(open(config_file))
        except IOError:
            self.logger.critical("Can't read config file: " + config_file)
            exit()

        self.api_access_token = config.get("Foursquare", "AccessToken")
        self.ics_filepath = config.get("Local", "IcsFilepath")
        self.kml_filepath = config.get("Local", "KmlFilepath")
        self.caldav_url = config.get("CalDAV", "url", fallback=None)
        self.caldav_username = config.get("CalDAV", "username", fallback=None)
        self.caldav_password = config.get("CalDAV", "password", fallback=None)
        self.caldav_calendar_name = config.get("CalDAV", "calendar_name", fallback="Foursquare")

    def generate(self, kind: str = "ics"):
        "Call this to fetch the data from the API and generate the file."
        if kind not in VALID_KINDS:
            raise ValueError("kind should be one of {}.".format(", ".join(VALID_KINDS)))

        if self.fetch == "all":
            checkins = self._get_all_checkins()
        else:
            checkins = self._get_recent_checkins()

        plural = "" if len(checkins) == 1 else "s"
        self.logger.info("Fetched {} checkin{} from the API".format(len(checkins), plural))

        if kind == "ics":
            filepath = self._generate_ics_file(checkins)
        elif kind == "kml":
            filepath = self._generate_kml_file(checkins)

        self.logger.info("Generated file {}".format(filepath))

    def _get_recent_checkins(self) -> list:
        "Make one request to the API for the most recent checkins."
        results = self._get_checkins_from_api()
        return results["checkins"]["items"]

    def _get_all_checkins(self) -> list:
        "Make multiple requests to the API to get ALL checkins."
        offset = 0
        checkins = []
        # Temporary total:
        total_checkins = 9999999999

        self.logger.debug("Fetching all checkins...")
        # Loop until we have fetched all checkins:
        while offset < total_checkins:
            results = self._get_checkins_from_api(offset)
            self.logger.debug("Got {} checkins from API with offset {}".format(
                results["checkins"]["count"], offset
            ))

            if offset == 0:
                # First time, set the correct total:
                total_checkins = results["checkins"]["count"]
                plural = "" if total_checkins == 1 else "s"
                self.logger.debug("{} checkin{} to fetch".format(total_checkins, plural))

            self.logger.debug("Fetched {}-{}".format(offset + 1, offset + 250))

            checkins += results["checkins"]["items"]
            offset += 250

        return checkins

    def _get_checkins_from_api(self, offset: int = 0) -> list:
        """Returns a list of recent checkins for the authenticated user.

        Keyword arguments:
        offset -- Integer, the offset number to send to the API.
                  The number of results to skip.
        """

        try:
            res = self.client.users.checkins(
                params={"limit": 250, "offset": offset, "sort": "newestfirst"}
            )
            self.logger.debug("Results: {}".format(res))
            return res
        except foursquare.FoursquareException as err:
            self.logger.error(
                "Error getting checkins, with offset of {}: {}".format(offset, err)
            )
            exit(1)

    def _get_user(self):
        "Returns details about the authenticated user."
        try:
            user = self.client.users()
        except foursquare.FoursquareException as err:
            self.logger.error("Error getting user: {}".format(err))
            exit(1)

        return user["user"]

    def _generate_ics_file(self, checkins: list) -> str:
        """Supplied with a list of checkin data from the API, generates
        and saves a .ics file.

        Returns the filepath of the saved file.

        Keyword arguments:
        checkins -- A list of dicts, each one data about a single checkin.
        """
        calendar = self._generate_calendar(checkins)

        with open(self.ics_filepath, "w") as f:
            f.writelines(calendar)

        return self.ics_filepath

    def _generate_calendar(self, checkins: list) -> Calendar:
        """Supplied with a list of checkin data from the API, generates
        an ics Calendar object and returns it.

        Keyword arguments:
        checkins -- A list of dicts, each one data about a single checkin.
        """
        user = self._get_user()

        c = Calendar()

        for checkin in checkins:
            if "venue" not in checkin:
                # I had some checkins with no data other than
                # id, createdAt and source.
                continue

            venue_name = checkin["venue"]["name"]
            tz_offset = self._get_checkin_timezone(checkin)

            e = Event()
            start = arrow.get(checkin["createdAt"]).replace(tzinfo=tz_offset)

            e.name = "@ {}".format(venue_name)
            e.location = venue_name
            e.url = "{}/checkin/{}".format(user["canonicalUrl"], checkin["id"])
            e.uid = checkin["id"]
            e.begin = start
            e.end = start + timedelta(minutes=15)
            e.created = start + timedelta(minutes=15)
            e.last_modified = start + timedelta(minutes=15)

            # Use the 'shout', if any, and the timezone offset in the
            # description.
            description = []
            if "shout" in checkin and len(checkin["shout"]) > 0:
                description = [checkin["shout"]]
            if "beenHere" in checkin and checkin["beenHere"]['lastCheckinExpiredAt'] > 0:
                description.append(
                    "It has been {} days since you last checked in here.".format(
                        (start - arrow.get(checkin["beenHere"]["lastCheckinExpiredAt"])).days
                    )
                )
            if "isMayor" in checkin and checkin["isMayor"]:
                description.append("At this time, you were the mayor of this venue!")
            e.description = "\n".join(description)

            # Use the venue_name and the address, if any, for the location.
            location = venue_name
            if "location" in checkin["venue"]:
                loc = checkin["venue"]["location"]
                if "formattedAddress" in loc and len(loc["formattedAddress"]) > 0:
                    address = ", ".join(loc["formattedAddress"])
                    location = "{}, {}".format(location, address)
            e.location = location

            c.events.add(e)

        return c

    def _generate_kml_file(self, checkins):
        """Supplied with a list of checkin data from the API, generates
        and saves a kml file.

        Returns the filepath of the saved file.

        Keyword arguments:
        checkins -- A list of dicts, each one data about a single checkin.
        """
        import simplekml

        user = self._get_user()

        kml = simplekml.Kml()

        # The original Foursquare files had a Folder with name and
        # description like this, so:
        names = [user.get("firstName", ""), user.get("lastName", "")]
        user_name = " ".join(names).strip()
        name = "foursquare checkin history for {}".format(user_name)
        fol = kml.newfolder(name=name, description=name)

        for checkin in checkins:
            if "venue" not in checkin:
                # I had some checkins with no data other than
                # id, createdAt and source.
                continue

            venue_name = checkin["venue"]["name"]
            tz_offset = self._get_checkin_timezone(checkin)
            url = "https://foursquare.com/v/{}".format(checkin["venue"]["id"])

            description = ['@<a href="{}">{}</a>'.format(url, venue_name)]
            if "shout" in checkin and len(checkin["shout"]) > 0:
                description.append('"{}"'.format(checkin["shout"]))
            description.append("Timezone offset: {}".format(tz_offset))

            coords = [
                (
                    checkin["venue"]["location"]["lng"],
                    checkin["venue"]["location"]["lat"],
                )
            ]

            visibility = 0 if "private" in checkin else 1

            pnt = fol.newpoint(
                name=venue_name,
                description="<![CDATA[{}]]>".format("\n".join(description)),
                coords=coords,
                visibility=visibility,
                # Both of these were set like this in Foursquare's original KML:
                altitudemode=simplekml.AltitudeMode.relativetoground,
                extrude=1,
            )

            # Foursquare's KML feeds had 'updated' and 'published' elements
            # in the Placemark, but I don't *think* those are standard, so:
            pnt.timestamp.when = arrow.get(
                checkin["createdAt"],
                tzinfo=self._get_checkin_timezone(checkin),
            ).isoformat()

            # Use the address, if any:
            if "location" in checkin["venue"]:
                loc = checkin["venue"]["location"]
                if "formattedAddress" in loc and len(loc["formattedAddress"]) > 0:
                    address = ", ".join(loc["formattedAddress"])
                    # While simplexml escapes other strings, it threw a wobbly
                    # over '&' in addresses, so escape them:
                    pnt.address = xml_escape(address)

        kml.save(self.kml_filepath)

        return self.kml_filepath

    def _get_checkin_timezone(self, checkin):
        """Given a checkin from the API, returns an arrow timezone object
        representing the timezone offset of that checkin.

        Keyword arguments
        checkin -- A dict of data about a single checkin
        """
        return tzoffset(None, checkin["timeZoneOffset"] * 60)

    def sync_calendar_to_caldav(self):
        """
        Syncs all events from the generated calendar to a CalDAV server.
        Uses credentials and URL from the instance config.
        """

        if self.fetch == "all":
            checkins = self._get_all_checkins()
        else:
            checkins = self._get_recent_checkins()
        calendar = self._generate_calendar(checkins)

        # Connect to CalDAV server using instance variables
        client = caldav.DAVClient(
            url=self.caldav_url,
            username=self.caldav_username,
            password=self.caldav_password,
        )
        principal = client.principal()

        # Try to find the calendar, or create it if it doesn't exist
        calendars = principal.calendars()
        self.logger.debug("Found {} calendars on the server".format(len(calendars)))
        cal = None
        for c in calendars:
            if c.name.strip() == self.caldav_calendar_name:
                cal = c
                self.logger.info("Found existing calendar: {}".format(cal.name))
                break
        if cal is None:
            self.logger.info("Creating new calendar: {}".format(self.caldav_calendar_name))
            cal = principal.make_calendar(name=self.caldav_calendar_name)

        self.logger.debug("Calendar has {} events".format(len(calendar.events)))
        # Upload each event from the ics.Calendar object
        for event in calendar.events:
            # Each event must have a unique UID
            # Use the event UID if present, otherwise generate a deterministic one from checkin ID
            if not event.uid:
                # Try to extract checkin ID from event.url or event.name as fallback
                checkin_id = None
                if hasattr(event, "url") and event.url:
                    # URL format: .../checkin/<checkin_id>
                    parts = event.url.rstrip("/").split("/")
                    if "checkin" in parts:
                        idx = parts.index("checkin")
                        if idx + 1 < len(parts):
                            checkin_id = parts[idx + 1]
                if not checkin_id and hasattr(event, "uid") and event.uid:
                    # fallback: try to parse from event.uid
                    if "@" in event.uid:
                        checkin_id = event.uid.split("@")[0]
                if not checkin_id:
                    # fallback: use event.name
                    checkin_id = event.name
                # Generate a repeatable UID using a namespace and checkin_id
                event.uid = "{}@foursquare.com".format(checkin_id)
            self.logger.debug("Uploading event with UID: {}".format(event.uid))
            cal.add_event(event.serialize())


def main():
    """Main function to parse arguments and run the FeedGenerator."""

    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Makes a .ics file from your Foursquare/Swarm checkins"
    )

    parser.add_argument(
        "--all",
        help="Fetch all checkins, not only the most recent",
        required=False,
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "-k",
        "--kind",
        action="store",
        help="Either ics, kml, or caldav. Default is ics.",
        choices=VALID_KINDS,
        default="ics",
        required=False,
        type=str,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="-v or --verbose for brief output; -vv for more.",
        required=False,
    )

    args = parser.parse_args()

    if args.verbose == 1:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level)

    if args.all:
        to_fetch = "all"
    else:
        to_fetch = "recent"

    generator = FeedGenerator(fetch=to_fetch)

    if args.kind == "caldav":
        generator.sync_calendar_to_caldav()
    else:
        # Generate the requested kind of file
        generator.generate(kind=args.kind)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())