# 🗺️ map2poster

**Create beautiful, minimalist map posters for any city in the world.**

`map2poster` is a high-performance Python tool that transforms OpenStreetMap data into stunning, gallery-ready minimalist art. Whether you're capturing the grid of New York, the canals of Venice, or the organic sprawl of Tokyo, `map2poster` delivers premium-quality visualizations with customizable themes and professional typography.

## ✨ Features

- **Global Coverage**: Fetch street networks, water bodies, and green spaces for any location on Earth.
- **Premium Themes**: Choose from 17+ curated color palettes (Noir, Terracotta, Neon Cyberpunk, etc.).
- **Vector Output**: Export as PNG, SVG, or PDF for high-resolution printing.
- **Precision Control**: Custom radius, dimensions, and coordinate overrides.
- **Multilingual Support**: Supports native scripts (CJK, Arabic, etc.) with automatic Google Fonts integration.
- **Fast & Efficient**: Local caching and optimized rendering pipeline.

## 🚀 Installation

### With `uv` (Recommended)

```bash
uv pip install map2poster
```

### With `pip`

```bash
pip install map2poster
```

## 🛠️ Usage

### Command Line Interface

Generate a poster instantly from your terminal:

```bash
map2poster --city "Paris" --country "France" --theme noir
```

| Option | Short | Description | Default |
| :--- | :--- | :--- | :--- |
| `--city` | `-c` | City name for geocoding | Required |
| `--country` | `-C` | Country name for geocoding | Required |
| `--theme` | `-t` | Theme name (noir, terracotta, etc.) | `terracotta` |
| `--distance` | `-d` | Map radius in meters | `18000` |
| `--format` | `-f` | Output format (png, svg, pdf) | `png` |
| `--list-themes` | | Show all available styles | |

### Python API

Integrate map generation into your own workflows:

```python
from map2poster import CreatePoster, load_theme, get_coordinates

# 1. Resolve location
coords = get_coordinates("Tokyo", "Japan")

# 2. Pick a style
theme = load_theme("japanese_ink")

# 3. Create the art
CreatePoster(
    city="Tokyo",
    country="Japan",
    point=coords,
    dist=12000,
    output_file="tokyo_poster.png",
    output_format="png",
    theme=theme
)
```

## 🎨 Themes

Capturing the mood of your city:

- **Noir**: Classic high-contrast black and white.
- **Terracotta**: Warm Mediterranean clay tones.
- **Neon Cyberpunk**: Electric pinks and cyans on deep indigo.
- **Midnight Blue**: Elegant navy and gold.
- **Blueprint**: Technical architectural aesthetic.
- *...and many more! Use `map2poster --list-themes` to see them all.*

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---
Created with ❤️ by **Anton Vice** ([a1996nton@gmail.com](mailto:a1996nton@gmail.com))
