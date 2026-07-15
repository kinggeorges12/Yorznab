from fastapi import APIRouter, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from collections import defaultdict
import xml.sax.saxutils as saxutils
from feedgen.feed import FeedGenerator
from feedgen.ext.torrent import TorrentExtension, TorrentEntryExtension
from datetime import datetime, timezone
import re

# Import local modules
from server.routers.handler import RouteHandler
from server.utils.feedconfig import FeedConfig
from utils.settings import AppSettings
from utils.keystore import KeyStore

router = APIRouter()

# Export config vars to globals
SETTINGS = AppSettings(filename='yorznab.yaml')
NS = {"torznab": "http://torznab.com/schemas/2015/feed"}

# Set default categories
CATEGORIES = [
    {'id': '2000', 'label': 'Movies', 'parent': None},
    {'id': '2010', 'label': 'Foreign', 'parent': '2000'},
    {'id': '2020', 'label': 'Other', 'parent': '2000'},
    {'id': '2030', 'label': 'SD', 'parent': '2000'},
    {'id': '2040', 'label': 'HD', 'parent': '2000'},
    {'id': '2045', 'label': 'UHD', 'parent': '2000'},
    {'id': '2050', 'label': 'BluRay', 'parent': '2000'},
    {'id': '2060', 'label': '3D', 'parent': '2000'},
    {'id': '5000', 'label': 'TV', 'parent': None},
    {'id': '5010', 'label': 'WEB-DL', 'parent': '5000'},
    {'id': '5020', 'label': 'Foreign', 'parent': '5000'},
    {'id': '5030', 'label': 'SD', 'parent': '5000'},
    {'id': '5040', 'label': 'HD', 'parent': '5000'},
    {'id': '5050', 'label': 'Other', 'parent': '5000'},
    {'id': '5060', 'label': 'Sport', 'parent': '5000'},
    {'id': '5070', 'label': 'Anime', 'parent': '5000'},
    {'id': '5080', 'label': 'Documentary', 'parent': '5000'},
]
def build_cats_tree(categories):
    """Build a mapping of category/subcategory IDs to their root parent category ID."""
    # Build quick dict of id -> parent
    parent_map = {c["id"]: c["parent"] for c in categories}
    lookup = {}
    def find_root(cat_id):
        # Follow parent chain until root
        parent = parent_map.get(cat_id)
        if parent is None:
            return cat_id
        return find_root(parent)
    for c in categories:
        lookup[c["id"]] = find_root(c["id"])
    return lookup
CAT_LOOKUP = build_cats_tree(CATEGORIES)

def cats_to_xml(categories_flat: list) -> str:
    """
    Generate <categories> XML from a flat list of dicts with keys: id, label, parent.
    Main categories have parent=None; subcategories reference parent ID.
    """
    # Group subcategories under parent
    grouped = defaultdict(list)
    main_cats = {}
    for cat in categories_flat:
        cat_id = cat["id"]
        label = cat["label"]
        parent = cat["parent"]
        if parent is None:
            main_cats[cat_id] = label
        else:
            grouped[parent].append((cat_id, label))
    
    # Sort main categories and subcategories by ID
    xml = "  <categories>\n"
    for cat_id in sorted(main_cats.keys()):
        label = saxutils.escape(main_cats[cat_id])
        xml += f'    <category id="{cat_id}" name="{label}">\n'
        for sub_id, sub_label in sorted(grouped.get(cat_id, [])):
            xml += f'      <subcat id="{sub_id}" name="{saxutils.escape(sub_label)}" />\n'
        xml += f'    </category>\n'
    xml += "  </categories>"
    return xml

def get_cat_id(parent, label):
    """Return the category id for a given parent and label."""
    parent_id = get_cat_id(None, parent) if parent is not None else None
    for cat in CATEGORIES:
        if (cat['parent'] is None or cat['parent'] == parent_id) and cat['label'].lower() == label.lower():
            return cat['id']
    return None  # not found

def filter_items(torrents, q=None, cat=None, extra_filters=None):
    """Filter torrents by q, cat_ids, and any additional filters."""
    # Start with default filters
    filters = []
    if q:
        # Replace any non-word characters or underscore with a regex search phrase to search the fileName
        q_pattern = re.sub(r'[\W_]+', r'[\\W_]*', re.escape(q))
        q_regex = re.compile(q_pattern, re.IGNORECASE)
        filters.append(lambda x, regex=q_regex: regex.search(x.get("fileName", "")))
    if cat:
        cat_ids = [c.strip() for c in cat.split(",") if c.strip()]
        filters.append(lambda x: any(
            (get_cat_id(x.get("type"), cat_label) in cat_ids) or
            (CAT_LOOKUP.get(get_cat_id(x.get("type"), cat_label)) in cat_ids)
            for cat_label in (lambda c=x.get("category", ["Other"]): c if isinstance(c, list) else [c])()
        ))
    # Merge in any extra filters
    if extra_filters:
        filters.extend(extra_filters)
    results = []
    for x in torrents:
        if all(f(x) for f in filters):
            results.append(x)

    return results

def generate_rss(items, offset=0, limit=0):
    global SETTINGS
    API_KEY = KeyStore.get_key("API_KEY")
    # Create feed using config
    fg = FeedGenerator()
    fg.load_extension('torrent')
    fg.title(SETTINGS.get('feed', 'title'))
    fg.link(href=SETTINGS.get('feed', 'link'))
    fg.description(SETTINGS.get('feed', 'description'))
    fg.language(SETTINGS.get('feed', 'language'))

    # Sort items first, then apply pagination
    sorted_items = sorted(items, key=lambda x: (x.get("score"), x.get("pubDate")), reverse=True)
    if limit == 0:
        limit = len(sorted_items) - offset
    paginated_items = sorted_items[offset:offset + limit]

    for t in paginated_items:
        fe = fg.add_entry()
        fe.id(t.get("descrLink"))
        fe.title(t.get("fileName"))
        # The link resets the permalink value, so set permalink=True below.
        # The relationship type (rel) must be enclosure for Sonarr to grab torrents.
        fe.link(href=t.get("fileUrl"))
        fe.enclosure(url=t.get("fileUrl"), length=t.get("fileSize", 0), type="application/x-bittorrent")
        fe.guid(guid=f"{SETTINGS.get('feed', 'link')}/api?apikey={API_KEY}&t=details&q={t.get('descrLink')}", permalink=True)
        pub_date = datetime.fromtimestamp(t.get("pubDate"), tz=timezone.utc)
        fe.pubDate(pub_date)
        # Look for category field and handle strings, then parse as array
        for cat_label in (lambda c=t.get("category", ["Other"]): c if isinstance(c, list) else [c])():
            fe.category(
                term=cat_label,
                scheme="http://torznab.com/categories",
                label=get_cat_id(t.get("type"), cat_label),
            )

        # Required Torznab attributes
        fe.torrent.filename(t["fileName"])
        fe.torrent.contentlength(str(t.get("fileSize", 0)))
        fe.torrent.seeds(str(t.get("nbSeeders", 0)))
        fe.torrent.peers(str(t.get("nbLeechers", 0)))

    return fg.rss_str(pretty=True)

# Default feed file
@router.get(RouteHandler.API)
async def base_endpoint(request: Request):
    global SETTINGS
    # Load first or default feed file
    feed = FeedConfig.feed()
    # Inject the feed parameter into the path
    redirect_url = f"{RouteHandler.API}/{feed}"
    # Append the original query string back onto the end if it exists
    query_string = request.url.query
    redirect_url += f"?{query_string}" if query_string else ""
    # Redirect to torznab_api handler
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get(RouteHandler.API + "/{feed}")
def torznab_api(
    feed: str,
    apikey: str = Query(None, description="API key from config file"),
    t: str = Query(..., description="Torznab function: caps, search, tvsearch, movie, details"),
    q: str = Query(None, description="Search query"),
    tvdbid: int = Query(None, description="TVDB ID for TV series search"),
    season: int = Query(None, description="Season number for TV series search"),
    ep: int = Query(None, description="Episode number within a season, or 0 for a full season download"),
    imdbid: int = Query(None, description="IMDB ID for movie search"),
    genre: str = Query(None, description="Genre defined by IMDB"),
    cat: str = Query(None, description="Comma-separated Torznab category IDs"),
    offset: int = Query(0, description="Number of results to skip"),
    limit: int = Query(0, description="Maximum number of results to return"),
):
    global SETTINGS, CATEGORIES, CAT_LOOKUP
    
    API_KEY = KeyStore.get_key("API_KEY")
    # API key check
    if apikey != API_KEY:
        apikey_error = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="{NS['torznab']}">
  <channel>
    <title>{SETTINGS.get('feed', 'title')}</title>
    <link>{SETTINGS.get('feed', 'link')}</link>
    <description>Indexer Error</description>
    <error code="1001" description="Missing or invalid API key"/>
  </channel>
</rss>"""
        return Response(content=apikey_error, media_type="application/xml", status_code=status.HTTP_401_UNAUTHORIZED)

    # Load torrents JSON after checking API key
    feed_config = FeedConfig.feed(feed)
    torrents = None
    if feed_config:
        torrents = feed_config.read()
    else:
        feed_error = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="{NS['torznab']}">
  <channel>
    <title>{SETTINGS.get('feed', 'title')}</title>
    <link>{SETTINGS.get('feed', 'link')}</link>
    <description>Feed Error</description>
    <error code="2" description="No feeds found"/>
  </channel>
</rss>"""
        return Response(content=feed_error, media_type="application/xml", status_code=status.HTTP_404_NOT_FOUND)
    
    if t == "caps":
        # Minimal caps XML
        caps_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<caps xmlns:torrent="{NS['torznab']}">
  <server version="1.0" title="{SETTINGS.get('feed', 'title')}" strapline="Yorznab Indexer"
      email="{SETTINGS.get('feed', 'email')}" url="{SETTINGS.get('feed', 'link')}"
      image="{SETTINGS.get('feed', 'image')}" />
  <limits max="0" default="0" />
  <retention>{SETTINGS.get('cron', 'retention_days')}</retention>
  <registration available="yes" open="yes" />

  <searching>
    <search available="yes" supportedParams="q,offset,limit" />
    <tv-search available="yes" supportedParams="q,tvdbid,season,ep,offset,limit" />
    <movie-search available="yes" supportedParams="q,imdbid,genre,offset,limit" />
    <audio-search available="no" supportedParams="q" />
    <book-search available="no" supportedParams="q" />
    <details available="yes" supportedParams="q" />
  </searching>

{cats_to_xml(CATEGORIES)}

  <tags>
    <tag name="anonymous" description="Uploader is anonymous" />
    <tag name="trusted" description="Uploader has high reputation" />
    <tag name="internal" description="Uploader is an internal release group" />
  </tags>
</caps>"""  # type: ignore
        return Response(content=caps_xml, media_type="application/xml")

    elif t == "search":
        # Return all items matching q (generic search)
        items = filter_items(torrents, q=q, cat=cat, extra_filters=None)
        return Response(content=generate_rss(items, offset, limit), media_type="application/xml")

    elif t == "tvsearch":
        # Filter TV items by q, season, ep
        items = filter_items(torrents, q=q, cat=cat, extra_filters=[
            lambda x: ("TV" in x.get("type")),
            lambda x: (tvdbid is None or x.get("tvdbid") == tvdbid),
            lambda x: (season is None or x.get("season") == season),
            lambda x: (ep is None or x.get("episode") == ep),
        ])
        return Response(content=generate_rss(items, offset, limit), media_type="application/xml")

    elif t == "movie":
        # Filter movie items
        items = filter_items(torrents, q=q, cat=cat, extra_filters=[
            lambda x: ("Movies" in x.get("type")),
            lambda x: (imdbid is None or x.get("imdbid") == imdbid),
            lambda x: (genre is None or genre in x.get("genre", [])),
        ])
        return Response(content=generate_rss(items, offset, limit), media_type="application/xml")

    elif t == "details":
        item = next((x for x in torrents if x.get("descrLink") == q), None)
        if not item:
            return Response(status_code=status.HTTP_404_NOT_FOUND, content="Item not found")
        return Response(content=generate_rss([item]), media_type="application/xml")

    else:
        return Response(content=f"<error>Unknown function t={t}</error>", media_type="application/xml")
