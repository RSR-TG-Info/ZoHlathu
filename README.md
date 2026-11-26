# zohlathu

A lightweight, zero-dependency Python package for fetching Mizo song lyrics from [zohlathu.in](https://www.zohlathu.in).

## Features

- No external dependencies (uses Python's standard library only)
- Handles typos, missing artist names, and common Mizo spelling variations
- Matches songs by title, artist, cover artist, composer, or lyric lines
- Built-in in-memory caching for faster repeat lookups

## Installation

Install the package using pip:

```bash
pip install zohlathu
```

To upgrade an existing installation:

```bash
pip install --upgrade zohlathu
```

## Usage

```python
from zohlathu import get_lyrics

song_name = "C. Sanga - Tawnmang Lasi"  # Replace with the song or artist you want to search
result = get_lyrics(song_name)

if result:
    response = (
        f"{result['title']}\n\n"
        f"{result['lyrics']}\n\n"
        f"Source: {result['source_url']}"
    )
    print(response)
else:
    print("Lyrics not found.")
```

### Returned Fields

`get_lyrics()` returns a dictionary with the following keys, or `None` if no confident match is found:

- `result['title']` — Full title (`Artist - Song`)
- `result['artist']` — Primary artist name
- `result['song']` — Song title
- `result['lyrics']` — Clean, formatted lyrics
- `result['source_url']` — Direct URL to the lyrics page
- `result['composers']` — List of composers or translators (if available)
- `result['also_performed_by']` — List of cover artists (if available)
- `result['youtube_url']` — YouTube video URL (if available)

## Error Handling

```python
from zohlathu import get_lyrics

try:
    song_name = "C. Sanga - Tawnmang Lasi"
    result = get_lyrics(song_name)

    if result:
        response = (
            f"{result['title']}\n\n"
            f"{result['lyrics']}\n\n"
            f"Source: {result['source_url']}"
        )
        print(response)
    else:
        print("No matching lyrics found.")
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
```

## Clearing the Cache

Results and the song index are cached in memory for 1 hour. To clear the cache manually:

```python
from zohlathu import clear_cache

clear_cache()
```

## Requirements

Requires Python 3.7+
