# Foursquare Feeds

A Python tool that downloads your check-ins from [Foursquare][4sq]/[Swarm][swarm] and converts them into calendar events. You can either generate an iCal (`.ics`) file or sync directly to a CalDAV server.

Perfect for keeping a record of your travels and activities in your preferred calendar application.

[4sq]: https://foursquare.com
[swarm]: https://www.swarmapp.com

## Features

- **iCal Export**: Generate `.ics` files that can be imported into any calendar application
- **CalDAV Sync**: Upload check-ins directly to CalDAV servers (Google Calendar, iCloud, etc.)
- **Flexible Fetching**: Get recent check-ins or your entire history
- **Rich Event Data**: Includes location details, notes (shouts), and check-in metadata

## Installation

This project requires Python 3.12+ and uses [uv](https://github.com/astral-sh/uv) for dependency management.

### 1. Install uv

If you don't have uv installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Set up the project

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/nikdoof/foursquare-feeds.git
cd foursquare-feeds
uv sync
```

### 3. Create a Foursquare app

1. Go to https://foursquare.com/developers/apps
2. Create a new App
3. Note your Client ID and Client Secret

### 4. Configure the application

Copy the example configuration file:

```bash
cp config_example.ini config.ini
```

Edit `config.ini` with your settings:

- **AccessToken**: Your Foursquare access token (see below)
- **IcsFilepath**: Where to save the `.ics` file (for local export)
- **CalDAV settings**: Your CalDAV server details (for direct sync)

## Getting an Access Token

You need a Foursquare access token to use this tool. Here are two methods:

### Method A: Quick Web-based Authentication

1. Visit https://your-foursquare-oauth-token.glitch.me
2. Follow the Foursquare login link
3. Accept the permissions
4. Copy the access token into your `config.ini`

*Thanks to [Simon Willison](https://github.com/dogsheep/swarm-to-sqlite/issues/4) for this tool.*

### Method B: Manual OAuth Flow

1. Set your app's Redirect URI to `http://localhost:8000/` in the Foursquare developer console
2. Run the following Python commands:

```python
import foursquare
client = foursquare.Foursquare(
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_CLIENT_SECRET',
    redirect_uri='http://localhost:8000'
)
print(client.oauth.auth_url())
```

3. Visit the printed URL in your browser
4. Copy the code from the redirect URL
5. Get your token:

```python
client.oauth.get_token('YOUR_CODE_HERE')
```

## Usage

### Generate an iCal file

Create a `.ics` file with your recent check-ins:

```bash
uv run ./generate_feeds.py
```

Get all your check-ins (may take a while):

```bash
uv run ./generate_feeds.py --all
```

### Sync to CalDAV

Upload check-ins directly to a CalDAV server:

```bash
uv run ./generate_feeds.py --kind caldav
```

Make sure your CalDAV settings are configured in `config.ini`.

## Configuration

The `config.ini` file supports these sections:

### [Foursquare]
- `AccessToken`: Your Foursquare API access token

### [Local]
- `IcsFilepath`: Path where the `.ics` file should be saved

### [CalDAV]
- `url`: Your CalDAV server URL
- `username`: CalDAV username
- `password`: CalDAV password
- `calendar_name`: Name of the calendar to create/use

## Command Line Options

### `--all`
Fetch all check-ins instead of just the recent 250:
```bash
uv run ./generate_feeds.py --all
```

### `--kind` / `-k`
Specify output type (`ics` or `caldav`):
```bash
uv run ./generate_feeds.py --kind ics
uv run ./generate_feeds.py --kind caldav
```

### `--verbose` / `-v`
Enable verbose output:
```bash
uv run ./generate_feeds.py -v        # Basic info
uv run ./generate_feeds.py -vv       # Detailed progress (with --all)
```

## What Gets Exported

Each check-in becomes a calendar event with:

- **Title**: "@ [Venue Name]"
- **Location**: Venue name and address
- **Time**: 15-minute event starting at check-in time
- **Description**: Your shout/comment, plus metadata like:
  - Days since last visit
  - Mayor status at the time
- **URL**: Link to the check-in on Foursquare

## Privacy Considerations

- Check-ins may contain private information
- If hosting `.ics` files publicly, use obscure filenames
- Consider filtering private check-ins before sharing

## About

**Original Author**: Phil Gyford
**Repository**: https://github.com/philgyford/foursquare-feeds

This tool exists because Foursquare's [official feeds](https://foursquare.com/feeds/) stopped working reliably. [Read more about the original motivation of Phil to create the tool](https://www.gyford.com/phil/writing/2019/05/13/foursquare-swarm-ical-feed/).
