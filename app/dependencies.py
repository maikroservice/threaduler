
class PostTooLongException(Exception):
    "Raised when the tweet character count is greater than platform allows"
    pass

class TweetNoQuoteAndMediaException(Exception):
    "Raised when the tweet is a quote but also contains media"
    pass

class NotionAPIKeyInvalid(Exception):
    "Notion API Key Invalid"
    pass


def notion_blocks_to_post_chunks(blocks):
    # split notion page content by divider and return a dictionary 
    # of raw notion blocks between two dividers
    chunks = {}
    counter = 0
    for block in blocks:
        if block["type"] == "divider":
            counter += 1
        else:
            try:
                chunks[counter].append(block)
            except KeyError:
                chunks[counter] = []
                chunks[counter].append(block)
    return chunks
