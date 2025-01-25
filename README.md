```from zohlathu import get_lyrics

# Usage
song_name = "C. Sanga - Tawnmang Lasi"  # Replace with your request song name
lyrics = get_lyrics(song_name) # Get the lyrics
if lyrics:
    # Format the response
    response = (
        f"{lyrics['title']}\n\n"
        f"{lyrics['lyrics']}\n\n"
        f"Source: {lyrics['source_url']}"
    )
    print(respose)```

● lyrics['title'] = The title of lyrics
● lyrics['lyrics'] = The lyrics
● lyrics['source_url'] = Link of the lyrics

#Handle Errors
```try:
    song_name = "C. Sanga - Tawnmang Lasi"  # Replace with your request song name
    lyrics = get_lyrics(song_name) # Get the lyrics
    if lyrics:
        # Format the response
        response = (
            f"{lyrics['title']}\n\n"
            f"{lyrics['lyrics']}\n\n"
            f"Source: {lyrics['source_url']}"
        )
        print(respose)
except Exception as e:
    print(f"An error occurred: {e}")```
