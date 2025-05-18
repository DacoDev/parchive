# Parchive

Parchive is a comprehensive podcast archiving tool that downloads, organizes, and manages podcast episodes with rich metadata support. It's designed to help you create complete archives of your favorite podcasts, including episode audio files, show and episode images, and detailed metadata.

## Features

- **Complete Podcast Archiving**: Download and store entire podcast feeds or selected episodes
- **Rich Metadata Support**: Store detailed information about shows and episodes
- **Image Downloading**: Automatically download podcast cover art and episode-specific images
- **Filesystem Organization**: Cleanly organized file structure with proper naming conventions
- **Database Management**: Maintain a searchable database of all shows and episodes
- **Sync Verification**: Scan for discrepancies between the database and downloaded files
- **User-Friendly CLI**: Interactive episode selection and discoverable commands
- **AI Analysis**: (Optional) Analyze podcast content with local AI models

## Installation

### Prerequisites

- Python 3.13+
- [Poetry](https://python-poetry.org/) for dependency management

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/parchive.git
cd parchive
```

2. Install dependencies with Poetry:
```bash
poetry install
```

3. Activate the virtual environment:
```bash
source $(poetry env info --path)/bin/activate
```

## Usage

### Basic Commands

```bash
# See all available commands
parchive --help

# Add a new podcast
parchive add-show

# List available list sub-commands
parchive list

# List all your saved shows
parchive list shows

# List episodes for a specific show
parchive list episodes <show_id>

# Download episodes (interactive mode)
parchive download <show_id>

# Download specific episodes
parchive download <show_id> --episodes <range>

# See available delete options
parchive delete

# Delete a show (both database entry and downloaded files)
parchive delete show <show_id> --all
```

### Adding Podcasts

```bash
parchive add-show
```
This interactive command will:
1. Ask for the feed URL
2. Parse the feed data and extract show metadata
3. Allow you to select which episodes to add (all, single, range)
4. Download the selected episodes and their images

### Downloading Episodes

Running `parchive download <show_id>` without additional parameters will start an interactive session that:

1. Prompts you to choose a download mode:
   - `all`: Download all episodes
   - `single`: Show episode list and download a specific episode
   - `range`: Download a range of episodes

If you prefer, you can specify the episodes directly with the `--episodes` option:

```bash
# Download all episodes
parchive download <show_id> --episodes all

# Download a specific episode
parchive download <show_id> --episodes 42

# Download a range of episodes
parchive download <show_id> --episodes 1-5,10,15-20
```

### Episode Selection

When specifying episode ranges, you can use:

- `all`: Download all episodes
- `single`: Download a single episode (you'll be prompted for the episode number)
- `range`: Download a range of episodes (e.g., `1-5,10,15-20`)
- Specific number (e.g., `42`): Download just that episode number

### Scanning and Fixing

The scan command identifies and optionally fixes mismatches between your database and filesystem:

```bash
# Scan a show and report issues
parchive scan <show_id>

# Scan and fix database issues
parchive scan <show_id> --fix

# Scan, fix, and delete orphaned files
parchive scan <show_id> --fix --force
```

### Analyzing Content (Optional)

If you have a local AI model server, you can analyze shows and episodes:

```bash
# Analyze a show
parchive analyze <show_id>

# Analyze a specific episode
parchive analyze <show_id> --episode <episode_number>
```

## Directory Structure

Parchive organizes downloads with this structure:

```
downloads/
└── <show_id>/
    ├── cover.jpg           # Show cover image
    ├── feed.xml            # Archived feed XML
    ├── metadata.json       # Show metadata
    ├── <ep_num>_<hash>.mp3 # Episode audio file
    └── <ep_num>_<hash>.jpg # Episode image file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
