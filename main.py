import streamlit as st
import os
import tempfile
import matplotlib
matplotlib.use('Agg')
from pathlib import Path
from PIL import Image
from map2poster import CreatePoster, load_theme, get_coordinates, get_available_themes, load_fonts

# Page Config
st.set_page_config(
    page_title="map2poster | Minimalist Map Art",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
    }
    .stDownloadButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def get_cached_coordinates(city, country):
    return get_coordinates(city, country)

@st.cache_data
def get_cached_theme(theme_name):
    return load_theme(theme_name)

def main():
    st.title("🗺️ map2poster")
    st.markdown("Generate beautiful, minimalist map posters for any city in the world.")

    # Sidebar
    with st.sidebar:
        st.header("📍 Location")
        city = st.text_input("City", value="New York")
        country = st.text_input("Country", value="USA")
        
        col1, col2 = st.columns(2)
        with col1:
            override_lat = st.text_input("Lat (optional)", placeholder="40.7128")
        with col2:
            override_lon = st.text_input("Lon (optional)", placeholder="-74.0060")

        st.divider()
        
        st.header("🎨 Style")
        themes = get_available_themes()
        selected_theme = st.selectbox("Theme", options=themes, index=themes.index("terracotta") if "terracotta" in themes else 0)
        
        st.header("📏 Dimensions")
        dist = st.slider("Radius (meters)", min_value=1000, max_value=30000, value=12000, step=1000)
        width = st.slider("Width (inches)", min_value=4.0, max_value=20.0, value=12.0, step=0.5)
        height = st.slider("Height (inches)", min_value=4.0, max_value=20.0, value=16.0, step=0.5)
        
        st.divider()
        
        st.header("🔡 Typography")
        display_city = st.text_input("Display Name (City)", value="")
        display_country = st.text_input("Display Name (Country)", value="")
        font_family = st.text_input("Google Font (Optional)", value="")
        
        st.divider()
        
        st.header("⚙️ Rendering")
        live_mode = st.checkbox("Live Render (Auto-update)", value=False)
        output_format = st.selectbox("Download Format", options=["png", "pdf", "svg"], index=0)
        
        st.divider()
        if st.button("🗑️ Clear Cache"):
            import shutil
            from map2poster.core import CACHE_DIR
            if CACHE_DIR.exists():
                shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(exist_ok=True)
                st.success("Cache cleared!")
                st.rerun()
            else:
                st.info("Cache is already empty.")

        generate_btn = st.button("🚀 Render Map", type="primary")

    # Main Area
    # In live mode, we trigger on any change unless the button is needed
    should_generate = generate_btn or live_mode

    if should_generate:
        # Define the task
        def generate():
            try:
                # 1. Handle coordinates
                if override_lat and override_lon:
                    point = [float(override_lat), float(override_lon)]
                else:
                    point = get_cached_coordinates(city, country)
                
                # 2. Setup theme
                theme = get_cached_theme(selected_theme)
                
                # 3. Create temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format.lower()}") as tmp:
                    output_path = tmp.name
                
                # 4. Generate poster
                custom_fonts = load_fonts(font_family) if font_family else None
                dpi = 72 if live_mode else 300
                CreatePoster(
                    city=city,
                    country=country,
                    point=point,
                    dist=dist,
                    output_file=output_path,
                    output_format=output_format,
                    theme=theme,
                    width=width,
                    height=height,
                    display_city=display_city if display_city else None,
                    display_country=display_country if display_country else None,
                    fonts=custom_fonts,
                    dpi=dpi
                )
                
                return output_path
            except Exception as e:
                st.error(f"Error: {e}")
                return None

        # Execute
        status_text = "Rendering preview..." if live_mode else "Fetching map data and rendering high-quality poster..."
        with st.spinner(status_text):
            file_path = generate()

        if file_path:
            # 5. Display result
            if output_format.lower() == "png":
                image = Image.open(file_path)
                st.image(image, use_container_width=True)
            else:
                st.info(f"Preview not available for {output_format.upper()}. Please download the file below.")
            
            # 6. Download button
            with open(file_path, "rb") as file:
                st.download_button(
                    label=f"💾 Download {output_format.upper()}",
                    data=file,
                    file_name=f"{city.lower()}_{selected_theme}.{output_format.lower()}",
                    mime=f"image/{output_format.lower()}" if output_format == "png" else "application/pdf" if output_format == "pdf" else "image/svg+xml"
                )
            
            # Cleanup
            try:
                os.remove(file_path)
            except:
                pass
    else:
        # Welcome Screen
        st.info("💡 Adjust the parameters in the sidebar and click **Render Map** to start.")
        
        st.subheader("Example Styles")
        cols = st.columns(4)
        for i, theme_name in enumerate(themes[:12]):
            with cols[i % 4]:
                st.markdown(f"🔹 **{theme_name.replace('_', ' ').title()}**")

if __name__ == "__main__":
    main()
