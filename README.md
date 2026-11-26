# zohlathu

A lightweight, zero-dependency Python package for fetching Mizo song lyrics from [zohlathu.in](https://www.zohlathu.in).

## Features

- No external dependencies (uses Python's standard library only)
- Supports direct Kristian Hla Bu (KHB) hymn number lookup (e.g. `khb 1`, `khb1`, `kristian hla bu 1`)
- Handles typos, missing artist names, and common Mizo shorthand (e.g. `bwite` for `bawihte`)
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

### Searching Songs

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

### Searching Kristian Hla Bu (KHB)

You can look up hymns directly by their KHB number using formats like `"khb 1"`, `"khb1"`, `"khb no 1"`, or `"kristian hla bu 1"`:

```python
from zohlathu import get_lyrics

hymn = get_lyrics("khb 1")

if hymn:
    print(f"{hymn['khb']} - {hymn['title']}\n")
    print(hymn["lyrics"])
else:
    print("Hymn not found.")
```

### Returned Fields

`get_lyrics()` returns a dictionary with the following keys, or `None` if no confident match is found:

- `result['title']` — Full title (`Artist - Song`, or hymn title)
- `result['artist']` — Primary artist name (empty string if not applicable)
- `result['song']` — Song title
- `result['khb']` — Kristian Hla Bu number (e.g. `"KHB 1"`, or empty string if not a KHB hymn)
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
