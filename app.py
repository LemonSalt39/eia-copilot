import streamlit as st
import folium
from streamlit_folium import st_folium
from openai import OpenAI
from pypdf import PdfReader
import re

# 1. Page Configuration
st.set_page_config(page_title="EIA Copilot - Northern Metropolis", layout="wide")
st.title("🌿 Northern Metropolis EIA Copilot")
st.caption("Agentic Spatial Planning & Official AFCD Biodiversity Intelligence running locally on Apple Silicon")

# 2. Connect to Local LM Studio Server
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

# 3. Northern Metropolis Strategic Locations & Polygonal Footprints
ZONE_DATA = {
    "San Tin Technopole": {
        "center": [22.502, 114.077],
        "polygon": [
            [22.515, 114.065],
            [22.518, 114.088],
            [22.495, 114.095],
            [22.490, 114.070]
        ],
        "default_zoom": 13,
        "desc": "Approx. 610 ha footprint; overlaps ~247 ha of wetland and active fishpond buffer."
    },
    "Mai Po Nature Reserve": {
        "center": [22.495, 114.038],
        "polygon": [
            [22.508, 114.030],
            [22.505, 114.050],
            [22.485, 114.045],
            [22.488, 114.025]
        ],
        "default_zoom": 14,
        "desc": "Ramsar Site wetland reserve and key East Asian-Australasian flyway for migratory birds."
    },
    "Kwu Tung North": {
        "center": [22.508, 114.110],
        "polygon": [
            [22.518, 114.100],
            [22.520, 114.125],
            [22.500, 114.120],
            [22.498, 114.098]
        ],
        "default_zoom": 13,
        "desc": "New Development Area integrated with the Long Valley Nature Park conservation zone."
    },
    "Lok Ma Chau Loop": {
        "center": [22.518, 114.073],
        "polygon": [
            [22.525, 114.065],
            [22.526, 114.080],
            [22.512, 114.082],
            [22.510, 114.068]
        ],
        "default_zoom": 14,
        "desc": "HK-Shenzhen Innovation & Technology Park with dedicated cross-boundary wildlife corridors."
    },
    "Hung Shui Kiu": {
        "center": [22.435, 113.995],
        "polygon": [
            [22.448, 113.985],
            [22.450, 114.010],
            [22.425, 114.008],
            [22.422, 113.988]
        ],
        "default_zoom": 13,
        "desc": "Western Economic Corridor high-density commercial and logistics planning hub."
    }
}

# Statutory EPD / AFCD Conservation Layers (Town Planning Board Guidelines TPB PG-NO. 12C)
STATUTORY_LAYERS = {
    "Wetland Conservation Area (WCA)": {
        "polygon": [
            [22.525, 114.020], [22.530, 114.055], [22.512, 114.075],
            [22.492, 114.068], [22.482, 114.045], [22.480, 114.020]
        ],
        "color": "#0066cc",
        "desc": "Statutory Wetland Conservation Area (WCA): Strict presumption against development to protect Deep Bay Ramsar Site fishponds."
    },
    "Wetland Buffer Area (WBA)": {
        "polygon": [
            [22.535, 114.015], [22.540, 114.068], [22.518, 114.090],
            [22.485, 114.085], [22.472, 114.050], [22.470, 114.015]
        ],
        "color": "#ff9900",
        "desc": "Statutory Wetland Buffer Area (WBA): 500m buffer strip requiring comprehensive Ecological Impact Assessment."
    }
}

# Verified AFCD Biodiversity Sighting Records (Source: DATA.GOV.HK / CSDI afcd_rcd_1665632148848_93995)
BIODIVERSITY_HOTSPOTS = [
    {
        "species": "Black-faced Spoonbill (Platalea minor)",
        "coords": [22.498, 114.035],
        "status": "Global Endangered (EN) | AFCD Class I Protection",
        "source": "AFCD BGIS / CSDI Portal",
        "notes": "Core intertidal mudflat roosting and feeding habitat in Inner Deep Bay."
    },
    {
        "species": "Eurasian Otter (Lutra lutra)",
        "coords": [22.508, 114.072],
        "status": "Regional Critically Endangered | Highly Sensitive",
        "source": "AFCD Ecological Survey 2024",
        "notes": "Recorded movement corridors across San Tin and Sam Pui Leng fishponds."
    },
    {
        "species": "Yellow-breasted Bunting (Emberiza aureola)",
        "coords": [22.512, 114.115],
        "status": "IUCN Critically Endangered (CR)",
        "source": "AFCD / Long Valley Monitoring",
        "notes": "Priority foraging stopover inside Long Valley Nature Park."
    },
    {
        "species": "Great Cormorant & Ardeid Night Roost",
        "coords": [22.520, 114.068],
        "status": "Regional Flyway Milestone",
        "source": "EPD Northern Link Baseline Survey",
        "notes": "Major night roost flight line intersecting the proposed Northern Link alignment."
    }
]

# 4. Helper: Extract text from ALL pages and count words safely
def extract_pdf_text(uploaded_file, max_words=10000):
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        total_pages = len(reader.pages)
        for i in range(total_pages):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text += f"\n--- Page {i+1} ---\n" + page_text
        
        words = text.split()
        word_count = len(words)
        if word_count > max_words:
            truncated_text = " ".join(words[:max_words])
            return truncated_text, total_pages, word_count, True
        return text, total_pages, word_count, False
    except Exception as e:
        return f"Error reading PDF: {e}", 0, 0, False

# 5. Initialize All Session State Variables (Protects against rerun cancellations)
if "active_location" not in st.session_state:
    st.session_state.active_location = "San Tin Technopole"

if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 13

if "pdf_context" not in st.session_state:
    st.session_state.pdf_context = ""

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": (
                "You are an expert environmental consultant and GIS spatial controller for Hong Kong's Northern Metropolis. "
                "Always cross-reference developer proposals against Hong Kong statutory planning guidelines, including:\n"
                "- Town Planning Board PG-No. 12C (Precautionary Approach & No-Net-Loss in Wetland Conservation Area / Wetland Buffer Area)\n"
                "- Protection of Endangered Species of Animals and Plants Ordinance (Cap. 586)\n"
                "- AFCD Priority Biodiversity occurrences (Black-faced Spoonbill, Eurasian Otter, Yellow-breasted Bunting)\n\n"
                "CRITICAL: When your response focuses on or navigates to a zone, include the exact navigation tag at the end:\n"
                "[NAVIGATE: location=San Tin Technopole, zoom=14]\n"
                "Allowed locations: San Tin Technopole, Mai Po Nature Reserve, Kwu Tung North, Lok Ma Chau Loop, Hung Shui Kiu."
            )
        },
        {
            "role": "assistant",
            "content": "Hello! I am your Northern Metropolis EIA Copilot. Upload an EIA Executive Summary PDF or ask me to audit project proposals against statutory Wetland Conservation Areas and AFCD species records."
        }
    ]

# 6. Sidebar: Document Ingestion (RAG) with Auto-Reset
with st.sidebar:
    st.header("📄 Document Ingestion (RAG)")
    
    with st.expander("❓ What Should I Download? (EIA Guide)", expanded=False):
        st.markdown(
            """
            Search the **[EPD EIAO Register](https://www.epd.gov.hk/eia/en/register/map_search.php)**:
            - **1. Project Profile (PP):** Preliminary scope.
            - **2. Study Brief (SB):** Statutory research checklist.
            - **3. EIA Report (Executive Summary) ⭐:** **BEST CHOICE!** Ingests full mitigation ratios & chapters.
            - **4. Environmental Permit (EP):** Legal conditions.
            """
        )
    
    uploaded_pdf = st.file_uploader("Upload Northern Metropolis EIA PDF", type=["pdf"], key="pdf_uploader")

    # Track uploaded filename in session state to handle file changes cleanly
    if "current_filename" not in st.session_state:
        st.session_state.current_filename = None

    # CASE 1: User cleared the uploaded file (clicked the 'X')
    if uploaded_pdf is None and st.session_state.current_filename is not None:
        st.session_state.pdf_context = ""
        st.session_state.current_filename = None
        st.info("🧹 Document removed. Context memory cleared.")

    # CASE 2: A new file was uploaded OR replaced
    elif uploaded_pdf is not None and uploaded_pdf.name != st.session_state.current_filename:
        with st.spinner(f"Reading '{uploaded_pdf.name}' and extracting text..."):
            extracted_text, total_pg, total_words, was_truncated = extract_pdf_text(uploaded_pdf)
            st.session_state.pdf_context = extracted_text
            st.session_state.current_filename = uploaded_pdf.name
            
            # Reposition map to match new document
            for loc in ZONE_DATA.keys():
                if loc.lower() in uploaded_pdf.name.lower() or loc.lower() in extracted_text.lower():
                    st.session_state.active_location = loc
                    st.session_state.map_zoom = ZONE_DATA[loc]["default_zoom"]
                    break

    # Show status and preview whenever a document is currently active
    if st.session_state.current_filename and st.session_state.pdf_context:
        words_count = len(st.session_state.pdf_context.split())
        st.success(f"✅ Active Document: **{st.session_state.current_filename}**")
        st.info(f"📖 Ingested: **{words_count:,} words** in working memory.")
        
        with st.expander("Preview Extracted Text (First 1,000 words)"):
            words_preview = " ".join(st.session_state.pdf_context.split()[:1000])
            st.text(words_preview + "\n\n... [Fed directly into AI context] ...")
            
# 7. Split UI: Chat on Left, Spatial Map on Right
col1, col2 = st.columns(2)

with col2:
    st.subheader("🗺️ Spatial Planning & Biodiversity Context")
    
    st.link_button(
        "🌐 Open Official EPD EIAO Map Portal", 
        "https://www.epd.gov.hk/eia/en/register/map_search.php",
        use_container_width=True
    )

    # Interactive Layer Toggles
    with st.expander("🎛️ Statutory Spatial Layer Controls", expanded=True):
        show_wca = st.checkbox("Show Statutory Wetland Conservation Area (WCA - Blue)", value=True, key="chk_wca")
        show_wba = st.checkbox("Show Statutory Wetland Buffer Area (WBA - Orange)", value=True, key="chk_wba")
        show_bio = st.checkbox("Show AFCD Protected Species Sightings (Pink Pins)", value=True, key="chk_bio")

    selected_loc = st.selectbox(
        "Focus Planning Area:", 
        list(ZONE_DATA.keys()), 
        index=list(ZONE_DATA.keys()).index(st.session_state.active_location),
        key="zone_selectbox"
    )
    
    if selected_loc != st.session_state.active_location:
        st.session_state.active_location = selected_loc
        st.session_state.map_zoom = ZONE_DATA[selected_loc]["default_zoom"]

    active_data = ZONE_DATA[st.session_state.active_location]

    # Render Interactive Hong Kong Map
    m = folium.Map(
        location=active_data["center"], 
        zoom_start=st.session_state.map_zoom, 
        tiles="OpenStreetMap"
    )

    # 1. Statutory Planning Buffers
    if show_wca:
        folium.Polygon(
            locations=STATUTORY_LAYERS["Wetland Conservation Area (WCA)"]["polygon"],
            color="#0066cc",
            weight=2,
            fill=True,
            fill_color="#0066cc",
            fill_opacity=0.25,
            tooltip="Statutory Wetland Conservation Area (WCA) - Strict No-Development Presumption"
        ).add_to(m)

    if show_wba:
        folium.Polygon(
            locations=STATUTORY_LAYERS["Wetland Buffer Area (WBA)"]["polygon"],
            color="#ff9900",
            weight=2,
            dash_array="6, 6",
            fill=True,
            fill_color="#ff9900",
            fill_opacity=0.15,
            tooltip="Statutory Wetland Buffer Area (WBA) - 500m Ecological Buffer Zone"
        ).add_to(m)

    # 2. AFCD Species Occurrences
    if show_bio:
        for spot in BIODIVERSITY_HOTSPOTS:
            folium.CircleMarker(
                location=spot["coords"],
                radius=8,
                color="#b0005d",
                weight=2,
                fill=True,
                fill_color="#e91e63",
                fill_opacity=0.85,
                tooltip=f"🐾 AFCD Record: {spot['species']}",
                popup=f"<b>{spot['species']}</b><br><b>Status:</b> {spot['status']}<br><b>Source:</b> {spot['source']}<br><i>{spot['notes']}</i>"
            ).add_to(m)

    # 3. Development Planning Zones
    for name, data in ZONE_DATA.items():
        is_selected = (name == st.session_state.active_location)
        
        folium.Marker(
            data["center"], 
            tooltip=name, 
            popup=f"<b>{name}</b><br>{data['desc']}",
            icon=folium.Icon(color="red" if is_selected else "green", icon="star" if is_selected else "info-sign")
        ).add_to(m)
        
        folium.Polygon(
            locations=data["polygon"],
            color="#FF3333" if is_selected else "#28A745",
            weight=3 if is_selected else 1,
            fill=True,
            fill_color="#FF3333" if is_selected else "#28A745",
            fill_opacity=0.35 if is_selected else 0.1,
            tooltip=f"{name} Development Footprint"
        ).add_to(m)

    # Dynamic map key prevents canvas refresh bugs
    map_render_key = f"map_{st.session_state.active_location}_{st.session_state.map_zoom}_{show_wca}_{show_wba}_{show_bio}"
    st_folium(m, width=550, height=500, key=map_render_key)
    st.caption(f"📍 **Active Zone Details:** {active_data['desc']}")

with col1:
    st.subheader("💬 EIA Regulatory Query")
    
    # Display Chat History
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                clean_content = re.sub(r"\[NAVIGATE:[^\]]+\]", "", msg["content"])
                st.markdown(clean_content)

    # User Input Handling
    if user_prompt := st.chat_input("Ask about EIA mitigation, wetland buffers, or species impacts..."):
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Context Augmentation via Uploaded PDF
        augmented_prompt = user_prompt
        if st.session_state.pdf_context:
            augmented_prompt += f"\n\n[CONTEXT FROM UPLOADED EIA DOCUMENT]:\n{st.session_state.pdf_context}"

        # Prepare messages payload
        api_messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in st.session_state.messages[:-1]
        ]
        api_messages.append({"role": "user", "content": augmented_prompt})

        # Query Local LM Studio Model with Visual Spinner
        with st.chat_message("assistant"):
            with st.spinner("🔍 Gemma is cross-referencing EIA text with AFCD statutory spatial layers..."):
                try:
                    stream = client.chat.completions.create(
                        model="local-model",
                        messages=api_messages,
                        stream=True,
                        temperature=0.2
                    )
                    full_response = st.write_stream(stream)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})

                    # Agentic Map Controller: Parse AI navigation commands
                    nav_match = re.search(r"\[NAVIGATE:\s*location=([^,\]]+)(?:,\s*zoom=(\d+))?\]", full_response)
                    
                    needs_rerun = False
                    if nav_match:
                        target_loc = nav_match.group(1).strip()
                        target_zoom = int(nav_match.group(2)) if nav_match.group(2) else 14
                        
                        if target_loc in ZONE_DATA:
                            if st.session_state.active_location != target_loc or st.session_state.map_zoom != target_zoom:
                                st.session_state.active_location = target_loc
                                st.session_state.map_zoom = target_zoom
                                needs_rerun = True

                    if not nav_match:
                        for loc in ZONE_DATA.keys():
                            if loc.lower() in user_prompt.lower():
                                if st.session_state.active_location != loc:
                                    st.session_state.active_location = loc
                                    st.session_state.map_zoom = ZONE_DATA[loc]["default_zoom"]
                                    needs_rerun = True
                                    break

                    if needs_rerun:
                        st.rerun()

                except Exception as e:
                    st.error(f"Cannot reach local model at localhost:1234. Is LM Studio active? Error: {e}")
