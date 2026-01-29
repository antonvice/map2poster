#!/usr/bin/env python3
"""
City Map Poster Generator - Core Module

This module generates beautiful, minimalist map posters for any city in the world.
It fetches OpenStreetMap data using OSMnx, applies customizable themes, and creates
high-quality poster-ready images with roads, water features, and parks.
"""

import asyncio
import json
import os
import pickle
import time
from datetime import datetime
from pathlib import Path
from typing import cast, Optional

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from geopandas import GeoDataFrame
from geopy.geocoders import Nominatim
from lat_lon_parser import parse
try:
    from .font_management import load_fonts
except (ImportError, ValueError):
    from font_management import load_fonts
from matplotlib.font_manager import FontProperties
from networkx import MultiDiGraph
from shapely.geometry import Point
from tqdm import tqdm

class CacheError(Exception):
    """Raised when a cache operation fails."""
    pass

# Fix: Use package-relative paths for resources
PACKAGE_ROOT = Path(__file__).parent
THEMES_DIR = PACKAGE_ROOT / "themes"
FONTS_DIR = PACKAGE_ROOT / "fonts"
POSTERS_DIR = Path("posters")

# Caching setup
CACHE_DIR_PATH = os.environ.get("CACHE_DIR", "cache")
CACHE_DIR = Path(CACHE_DIR_PATH)
CACHE_DIR.mkdir(exist_ok=True)

# Default fonts loaded at module level for convenience
FONTS = load_fonts()

def _cache_path(key: str) -> Path:
    """Generate a safe cache file path from a cache key."""
    import hashlib
    hash_key = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{hash_key}.pkl"

def cache_get(key: str):
    """Retrieve a cached object by key."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except (EOFError, pickle.UnpicklingError, Exception):
        # Corrupted file, delete it and pretend it doesn't exist
        try:
            path.unlink()
        except:
            pass
        return None

def cache_set(key: str, value):
    """Store an object in the cache."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        path = _cache_path(key)
        with open(path, "wb") as f:
            pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        raise CacheError(f"Cache write failed: {e}") from e

def is_latin_script(text):
    """Check if text is primarily Latin script."""
    if not text:
        return True
    latin_count = 0
    total_alpha = 0
    for char in text:
        if char.isalpha():
            total_alpha += 1
            if ord(char) < 0x250:
                latin_count += 1
    if total_alpha == 0:
        return True
    return (latin_count / total_alpha) > 0.8

def generate_output_filename(city, theme_name, output_format):
    """Generate unique output filename."""
    if not POSTERS_DIR.exists():
        POSTERS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(" ", "_")
    ext = output_format.lower()
    filename = f"{city_slug}_{theme_name}_{timestamp}.{ext}"
    return str(POSTERS_DIR / filename)

def get_available_themes():
    """Returns a list of available theme names."""
    if not THEMES_DIR.exists():
        return []
    themes = []
    for file in sorted(os.listdir(THEMES_DIR)):
        if file.endswith(".json"):
            themes.append(file[:-5])
    return themes

def load_theme(theme_name="terracotta"):
    """Load theme from JSON file."""
    theme_file = THEMES_DIR / f"{theme_name}.json"
    if not theme_file.exists():
        # Fallback to embedded terracotta theme
        return {
            "name": "Terracotta",
            "description": "Mediterranean warmth",
            "bg": "#F5EDE4",
            "text": "#8B4513",
            "gradient_color": "#F5EDE4",
            "water": "#A8C4C4",
            "parks": "#E8E0D0",
            "road_motorway": "#A0522D",
            "road_primary": "#B8653A",
            "road_secondary": "#C9846A",
            "road_tertiary": "#D9A08A",
            "road_residential": "#E5C4B0",
            "road_default": "#D9A08A",
        }
    with open(theme_file, "r") as f:
        return json.load(f)

def create_gradient_fade(ax, color, location="bottom", zorder=10):
    """Creates a fade effect."""
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))
    rgb = mcolors.to_rgb(color)
    my_colors = np.zeros((256, 4))
    my_colors[:, 0:3] = rgb
    if location == "bottom":
        my_colors[:, 3] = np.linspace(1, 0, 256)
        extent_y = (0, 0.25)
    else:
        my_colors[:, 3] = np.linspace(0, 1, 256)
        extent_y = (0.75, 1.0)
    custom_cmap = mcolors.ListedColormap(my_colors)
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_range = ylim[1] - ylim[0]
    ax.imshow(
        gradient,
        extent=[xlim[0], xlim[1], ylim[0] + y_range * extent_y[0], ylim[0] + y_range * extent_y[1]],
        aspect="auto",
        cmap=custom_cmap,
        zorder=zorder,
        origin="lower",
    )

def get_edge_colors_by_type(g, theme):
    """Assigns colors to edges based on road type hierarchy."""
    edge_colors = []
    for _, _, data in g.edges(data=True):
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'
        if highway in ["motorway", "motorway_link"]:
            color = theme["road_motorway"]
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            color = theme["road_primary"]
        elif highway in ["secondary", "secondary_link"]:
            color = theme["road_secondary"]
        elif highway in ["tertiary", "tertiary_link"]:
            color = theme["road_tertiary"]
        elif highway in ["residential", "living_street", "unclassified"]:
            color = theme["road_residential"]
        else:
            color = theme.get('road_default', '#888888')
        edge_colors.append(color)
    return edge_colors

def get_edge_widths_by_type(g):
    """Assigns line widths to edges based on road type."""
    edge_widths = []
    for _, _, data in g.edges(data=True):
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list):
            highway = highway[0] if highway else 'unclassified'
        if highway in ["motorway", "motorway_link"]:
            width = 1.2
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            width = 1.0
        elif highway in ["secondary", "secondary_link"]:
            width = 0.8
        elif highway in ["tertiary", "tertiary_link"]:
            width = 0.6
        else:
            width = 0.4
        edge_widths.append(width)
    return edge_widths

def get_coordinates(city, country):
    """Fetches coordinates for a given city and country."""
    cache_key = f"coords_{city.lower()}_{country.lower()}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    geolocator = Nominatim(user_agent="city_map_poster", timeout=10)
    time.sleep(1)
    try:
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            res = (location.latitude, location.longitude)
            cache_set(cache_key, res)
            return res
    except Exception as e:
        raise ValueError(f"Geocoding failed for {city}, {country}: {e}") from e
    raise ValueError(f"Could not find coordinates for {city}, {country}")

def get_crop_limits(g_proj, center_lat_lon, fig, dist):
    """Crop inward to preserve aspect ratio."""
    lat, lon = center_lat_lon
    center = ox.projection.project_geometry(Point(lon, lat), crs="EPSG:4326", to_crs=g_proj.graph["crs"])[0]
    center_x, center_y = center.x, center.y
    fig_width, fig_height = fig.get_size_inches()
    aspect = fig_width / fig_height
    half_x = dist
    half_y = dist
    if aspect > 1:
        half_y = half_x / aspect
    else:
        half_x = half_y * aspect
    return ((center_x - half_x, center_x + half_x), (center_y - half_y, center_y + half_y))

def fetch_graph(point, dist) -> Optional[MultiDiGraph]:
    """Fetch street network graph."""
    lat, lon = point
    cache_key = f"graph_{lat}_{lon}_{dist}"
    print(f"[{time.strftime('%H:%M:%S')}]   - Checking cache for graph...")
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[{time.strftime('%H:%M:%S')}]   - Cache hit!")
        return cast(MultiDiGraph, cached)
    
    print(f"[{time.strftime('%H:%M:%S')}]   - Cache miss. Downloading from OSM (this may take a while for large areas)...")
    try:
        g = ox.graph_from_point(point, dist=dist, dist_type='bbox', network_type='all', truncate_by_edge=True)
        print(f"[{time.strftime('%H:%M:%S')}]   - Download complete. Saving to cache...")
        time.sleep(0.5)
        cache_set(cache_key, g)
        return g
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]   - OSMnx error: {e}")
        return None

def fetch_features(point, dist, tags, name) -> Optional[GeoDataFrame]:
    """Fetch geographic features."""
    lat, lon = point
    tag_str = "_".join(tags.keys())
    cache_key = f"{name}_{lat}_{lon}_{dist}_{tag_str}"
    print(f"[{time.strftime('%H:%M:%S')}]   - Checking cache for {name}...")
    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[{time.strftime('%H:%M:%S')}]   - Cache hit for {name}!")
        return cast(GeoDataFrame, cached)
    
    print(f"[{time.strftime('%H:%M:%S')}]   - Cache miss. Downloading {name} from OSM...")
    try:
        data = ox.features_from_point(point, tags=tags, dist=dist)
        print(f"[{time.strftime('%H:%M:%S')}]   - Download complete for {name}.")
        time.sleep(0.3)
        cache_set(cache_key, data)
        return data
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]   - OSMnx error fetching {name}: {e}")
        return None

def create_poster(
    city,
    country,
    point,
    dist,
    output_file,
    output_format,
    theme=None,
    width=12,
    height=16,
    country_label=None,
    display_city=None,
    display_country=None,
    fonts=None,
    dpi=300,
):
    """Generate a complete map poster."""
    print(f"[{time.strftime('%H:%M:%S')}] 🚀 Starting poster generation for {city}...")
    if theme is None:
        theme = load_theme("terracotta")
    
    display_city = display_city or city
    display_country = display_country or country_label or country

    compensated_dist = dist * (max(height, width) / min(height, width)) / 4
    print(f"[{time.strftime('%H:%M:%S')}] 🔍 Fetching street network (dist={compensated_dist:.0f}m)...")
    g = fetch_graph(point, compensated_dist)
    if g is None:
        raise RuntimeError("Failed to retrieve street network data.")
    
    print(f"[{time.strftime('%H:%M:%S')}] 🌊 Fetching water features...")
    water = fetch_features(point, compensated_dist, {"natural": "water", "waterway": "riverbank"}, "water")
    print(f"[{time.strftime('%H:%M:%S')}] 🌳 Fetching park features...")
    parks = fetch_features(point, compensated_dist, {"leisure": "park", "landuse": "grass"}, "parks")

    print(f"[{time.strftime('%H:%M:%S')}] 🎨 Initializing plot...")
    fig, ax = plt.subplots(figsize=(width, height), facecolor=theme["bg"])
    ax.set_facecolor(theme["bg"])
    ax.set_position((0.0, 0.0, 1.0, 1.0))
    
    print(f"[{time.strftime('%H:%M:%S')}] 🗺️ Projecting graph...")
    g_proj = ox.project_graph(g)

    if water is not None and not water.empty:
        print(f"[{time.strftime('%H:%M:%S')}] 🖌️ Rendering water...")
        water_polys = water[water.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if not water_polys.empty:
            water_polys = water_polys.to_crs(g_proj.graph['crs'])
            water_polys.plot(ax=ax, facecolor=theme['water'], edgecolor='none', zorder=0.5)

    if parks is not None and not parks.empty:
        print(f"[{time.strftime('%H:%M:%S')}] 🖌️ Rendering parks...")
        parks_polys = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if not parks_polys.empty:
            parks_polys = parks_polys.to_crs(g_proj.graph['crs'])
            parks_polys.plot(ax=ax, facecolor=theme['parks'], edgecolor='none', zorder=0.8)

    print(f"[{time.strftime('%H:%M:%S')}] 🛣️ Processing edge colors and widths...")
    edge_colors = get_edge_colors_by_type(g_proj, theme)
    edge_widths = get_edge_widths_by_type(g_proj)
    crop_xlim, crop_ylim = get_crop_limits(g_proj, point, fig, compensated_dist)
    
    print(f"[{time.strftime('%H:%M:%S')}] 🖌️ Rendering roads...")
    ox.plot_graph(
        g_proj, ax=ax, bgcolor=theme['bg'],
        node_size=0, edge_color=edge_colors, edge_linewidth=edge_widths,
        show=False, close=False,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(crop_xlim)
    ax.set_ylim(crop_ylim)

    print(f"[{time.strftime('%H:%M:%S')}] ✨ Applying gradients...")
    create_gradient_fade(ax, theme['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, theme['gradient_color'], location='top', zorder=10)

    print(f"[{time.strftime('%H:%M:%S')}] 🔤 Adding text labels...")
    scale_factor = min(height, width) / 12.0
    active_fonts = fonts or FONTS
    
    if active_fonts:
        font_sub = FontProperties(fname=active_fonts["light"], size=22 * scale_factor)
        font_coords = FontProperties(fname=active_fonts["regular"], size=14 * scale_factor)
        font_attr = FontProperties(fname=active_fonts["light"], size=8 * scale_factor)
    else:
        font_sub = FontProperties(family="monospace", size=22 * scale_factor)
        font_coords = FontProperties(family="monospace", size=14 * scale_factor)
        font_attr = FontProperties(family="monospace", size=8 * scale_factor)

    spaced_city = "  ".join(list(display_city.upper())) if is_latin_script(display_city) else display_city
    city_char_count = len(display_city)
    base_size = 60 * scale_factor
    adjusted_font_size = base_size * (10 / city_char_count) if city_char_count > 10 else base_size
    
    if active_fonts:
        font_main = FontProperties(fname=active_fonts["bold"], size=max(adjusted_font_size, 10 * scale_factor))
    else:
        font_main = FontProperties(family="monospace", weight="bold", size=max(adjusted_font_size, 10 * scale_factor))

    ax.text(0.5, 0.14, spaced_city, transform=ax.transAxes, color=theme["text"], ha="center", fontproperties=font_main, zorder=11)
    ax.text(0.5, 0.10, display_country.upper(), transform=ax.transAxes, color=theme["text"], ha="center", fontproperties=font_sub, zorder=11)
    
    lat, lon = point
    coord_text = f"{abs(lat):.4f}° {'N' if lat>=0 else 'S'} / {abs(lon):.4f}° {'E' if lon>=0 else 'W'}"
    ax.text(0.5, 0.07, coord_text, transform=ax.transAxes, color=theme["text"], alpha=0.7, ha="center", fontproperties=font_coords, zorder=11)
    ax.plot([0.4, 0.6], [0.125, 0.125], transform=ax.transAxes, color=theme["text"], linewidth=1 * scale_factor, zorder=11)
    ax.text(0.98, 0.02, "© OpenStreetMap contributors", transform=ax.transAxes, color=theme["text"], alpha=0.5, ha="right", va="bottom", fontproperties=font_attr, zorder=11)

    print(f"[{time.strftime('%H:%M:%S')}] 💾 Saving file ({output_format}, dpi={dpi})...")
    plt.savefig(output_file, format=output_format.lower(), facecolor=theme["bg"], bbox_inches="tight", pad_inches=0.05, dpi=dpi if output_format.lower() == "png" else None)
    plt.close()
    print(f"[{time.strftime('%H:%M:%S')}] ✅ Done!")

def list_themes():
    """List all available themes."""
    available_themes = get_available_themes()
    print("\nAvailable Themes:")
    for theme_name in available_themes:
        theme = load_theme(theme_name)
        print(f"  {theme_name}: {theme.get('description', '')}")

def print_examples():
    """Print usage examples."""
    print("Example: map2poster --city Paris --country France --theme noir")
