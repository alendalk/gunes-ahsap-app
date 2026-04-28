import streamlit as st
import pandas as pd
import math
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

# ─── Sayfa Ayarları ──────────────────────────────────────────────────────────
st.set_page_config(page_title="Güneş Ahşap Ambalaj", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #1a1a1a; color: #f0e6d3; }
    .main-header {
        background: linear-gradient(135deg, #8B4513 0%, #D2691E 50%, #CD853F 100%);
        padding: 20px 30px; border-radius: 12px; margin-bottom: 25px;
        text-align: center; box-shadow: 0 4px 20px rgba(139,69,19,0.4);
    }
    .main-header h1 { color: #FFF8DC; font-size: 2rem; margin: 0; letter-spacing: 2px; }
    .main-header p  { color: #FFE4B5; margin: 4px 0 0; font-size: 0.95rem; opacity: 0.9; }
    .result-card {
        background: #2a2a2a; border: 1px solid #8B4513;
        border-left: 4px solid #D2691E; border-radius: 8px;
        padding: 16px 20px; margin: 8px 0;
    }
    .result-card .label { font-size: 0.85rem; color: #CD853F; text-transform: uppercase; letter-spacing: 1px; }
    .result-card .value { font-size: 1.6rem; font-weight: bold; color: #FFF8DC; margin-top: 4px; }
    [data-testid="stSidebar"] { background-color: #0f0f0f !important; border-right: 2px solid #8B4513; }
    .stButton > button {
        background: linear-gradient(135deg, #8B4513, #D2691E);
        color: #FFF8DC; border: none; border-radius: 8px;
        padding: 10px 30px; font-weight: bold; letter-spacing: 1px;
        width: 100%; transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #A0522D, #E07B30);
        box-shadow: 0 4px 15px rgba(210,105,30,0.5); transform: translateY(-1px);
    }
    .stNumberInput input, .stTextInput input {
        background-color: #2a2a2a !important; color: #f0e6d3 !important;
        border: 1px solid #8B4513 !important; border-radius: 6px !important;
    }
    h3 { color: #CD853F !important; border-bottom: 1px solid #8B4513; padding-bottom: 8px; }
    hr { border-color: #8B4513 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Malzeme Fiyatları (SİPARİŞ!L4, N4, P4) ─────────────────────────────────
KONTRPLAK_TL  = 44000   # ₺/m³  — SİPARİŞ!L4
AHSAP_TL      = 24000   # ₺/m³  — SİPARİŞ!N4
SAC_TL        = 60      # ₺/kg  — SİPARİŞ!P4
BASKI_TL      = 1       # ₺/ad  — SİPARİŞ!R4
IP_TL         = 1       # ₺/ad  — SİPARİŞ!T4
ALU_FOLYO_TL  = 40      # ₺/m²  — SİPARİŞ!V4
VCI_TORBA_TL  = 40      # ₺/ad  — SİPARİŞ!X4
NEM_ALICI_TL  = 7       # ₺/ad  — SİPARİŞ!Z4
KDV           = 0.20
ISCILIK_ARTIS = 0.18    # %18 — SİPARİŞ!AE11

DATA_FILE = "teklifler.csv"

# ─── KAFES AHŞAP SANDIK hesaplama (KAFES_AHŞAP_SANDIK + KATLANIR sayfaları) ──
def kafes_sandik_hesapla(boy_cm, en_cm, yuk_cm, adet, kalinlik=0.6, kapak_ad=2):
    """
    Excel KAFES_AHŞAP_SANDIK + KATLANIR sayfasındaki formülleri Python'a aktarır.
    Girişler cm, çıkış ₺.
    """
    # mm'ye çevir (Excel mm cinsinden çalışıyor)
    boy = boy_cm * 10
    en  = en_cm  * 10
    yuk = yuk_cm * 10
    kal = kalinlik * 10  # mm

    # GÖVDE DİKEY/YATAY tahtalar: 10mm en, 2.1mm kalınlık (KAFES_AHŞAP_SANDIK!E4,F4)
    govde_en  = 10
    govde_kal = 2.1

    # ÖN DUVAR DİKME adedi: J4 formülü
    if boy < 1290:
        on_dikme = 2
    elif boy < 2000:
        on_dikme = 3
    else:
        on_dikme = 4

    # Yatay tahta adedi: K4 = YUK/GOVDE_YATAY
    yatay_ad = math.ceil(yuk / govde_en)

    # YAN DUVAR DİKME adedi: M4
    if en < 1090:
        yan_dikme = 2
    elif en < 2000:
        yan_dikme = 3
    else:
        yan_dikme = 4

    # KAPAK YATAYı: Q4 = kapak_genislik * boy / (govde_en*100)
    kapak_oran = kapak_ad * en / (govde_en * 10) / 100  # doluluk oranı
    
    # Ahşap m³ hesabı (KAFES_AHŞAP_SANDIK!I4 = V4+AA4+AF4+AK4+AP4+AU4)
    # ÖN DUVAR DİKME (V4)
    R4 = (yuk + govde_kal*2 + govde_kal*2) / 10 - 1  # cm
    v4 = R4 * govde_en * govde_kal * (on_dikme*2) / 1_000_000

    # ÖN DUVAR YATAY (AA4)
    w4 = (boy + govde_kal*2 + govde_kal*2) / 10
    aa4 = w4 * govde_en * govde_kal * (yatay_ad * 2) / 1_000_000

    # YAN DUVAR DİKME (AF4)
    ab4 = R4
    af4 = ab4 * govde_en * govde_kal * (yan_dikme*2) / 1_000_000

    # YAN DUVAR YATAY (AK4)
    ag4 = (en + govde_kal*2 + govde_kal*2) / 10
    ak4 = ag4 * govde_en * govde_kal * (yatay_ad * 2) / 1_000_000

    # KAPAK DİKME (AP4)
    al4 = ag4
    ao4 = on_dikme
    ap4 = al4 * govde_en * govde_kal * ao4 / 1_000_000

    # KAPAK YATAY (AU4) — kapalı oran
    au4 = w4 * govde_en * govde_kal * kapak_oran / 1_000_000

    ahsap_m3 = (v4 + aa4 + af4 + ak4 + ap4 + au4) * adet

    # Maliyet
    ahsap_maliyet = ahsap_m3 * AHSAP_TL

    # İşçilik artışı (%18 — SİPARİŞ!AE11)
    birim_maliyet  = ahsap_maliyet / adet if adet else 0
    artis_tl       = birim_maliyet * ISCILIK_ARTIS
    birim_fiyat    = birim_maliyet + artis_tl
    toplam_fiyat   = birim_fiyat * adet
    kdv_tutari     = toplam_fiyat * KDV
    kdv_dahil      = toplam_fiyat + kdv_tutari

    return {
        "ahsap_m3":    round(ahsap_m3, 6),
        "maliyet":     round(ahsap_maliyet, 2),
        "birim_fiyat": round(birim_fiyat, 2),
        "toplam":      round(toplam_fiyat, 2),
        "kdv_tutari":  round(kdv_tutari, 2),
        "kdv_dahil":   round(kdv_dahil, 2),
    }


# ─── PALET hesaplama (PALET + SİPARİŞ sayfaları) ─────────────────────────────
def palet_hesapla(boy_cm, en_cm, yuk_cm, adet, palet_tipi=4):
    """
    PALET sayfası formüllerini Python'a aktarır.
    palet_tipi: 4=KADRAJ 10*10 TAM KAPALI (varsayılan), diğerleri de desteklenir.
    """
    boy = boy_cm  # cm
    en  = en_cm
    yuk = yuk_cm

    TAHTA_EN  = 10   # mm — B3
    TAHTA_KAL = 2.6  # mm — H3
    TAKOZ_EN  = 10   # mm — J3
    TAKOZ_YUK = 10   # mm

    # Palet tipi 4 = KADRAJ 10*10 TAM KAPALI
    # ÜST TAHTA adedi: U13 formülü → type4: L7/AA3 (en/ayak_en → en/10)
    ust_tahta_ad = math.ceil(en / TAHTA_EN)
    # ALT AYAK adedi: U14 → type4: A9 = boy'a göre
    if boy < 69:
        boy_ad = 2
    elif boy < 171:
        boy_ad = 3
    elif boy < 209:
        boy_ad = 4
    else:
        boy_ad = 5

    # X13: ÜST TAHTA m³ = boy * tahta_en * tahta_kal * ust_tahta_ad / 1e6
    x13 = boy * TAHTA_EN * TAHTA_KAL * ust_tahta_ad / 1_000_000
    # X14: ALT AYAK m³ = en * takoz_en * takoz_yuk * boy_ad / 1e6
    x14 = en * TAKOZ_EN * TAKOZ_YUK * boy_ad / 1_000_000
    # O18: Toplam ahşap m³ (palet)
    o18 = x13 + x14

    # Kontrplak m³ (KATLANIR!X3 formülü — temel sandık için 0)
    # PALET kendi başına ahşap odaklı → kontrplak yok
    
    # Ahşap birim maliyet
    ahsap_birim_m3  = o18
    ahsap_maliyet   = ahsap_birim_m3 * AHSAP_TL
    
    # İşçilik + artış
    artis_tl        = ahsap_maliyet * ISCILIK_ARTIS
    birim_fiyat     = ahsap_maliyet + artis_tl
    toplam_fiyat    = birim_fiyat * adet
    kdv_tutari      = toplam_fiyat * KDV
    kdv_dahil       = toplam_fiyat + kdv_tutari

    return {
        "ahsap_m3":    round(ahsap_birim_m3, 6),
        "maliyet":     round(ahsap_maliyet, 2),
        "birim_fiyat": round(birim_fiyat, 2),
        "toplam":      round(toplam_fiyat, 2),
        "kdv_tutari":  round(kdv_tutari, 2),
        "kdv_dahil":   round(kdv_dahil, 2),
    }


# ─── PDF ─────────────────────────────────────────────────────────────────────
def teklif_pdf_olustur(musteri, urun, fiyat, aciklama):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    title_s = ParagraphStyle("t", fontSize=18, fontName="Helvetica-Bold",
                             textColor=colors.HexColor("#8B4513"), spaceAfter=6, alignment=1)
    sub_s   = ParagraphStyle("s", fontSize=11, fontName="Helvetica",
                             textColor=colors.HexColor("#555555"), spaceAfter=4, alignment=1)
    note_s  = ParagraphStyle("n", fontSize=9, fontName="Helvetica",
                             textColor=colors.HexColor("#888888"), alignment=1)

    els = []
    els.append(Paragraph("GÜNEŞ AHŞAP AMBALAJ", title_s))
    els.append(Paragraph("Ahşap Ambalaj Çözümleri", sub_s))
    els.append(Spacer(1, 0.5*cm))

    divider = Table([[""]], colWidths=[doc.width],
                    style=TableStyle([("LINEABOVE",(0,0),(-1,0),1.5,colors.HexColor("#8B4513"))]))
    els.append(divider)
    els.append(Spacer(1, 0.4*cm))

    els.append(Paragraph("TEKLİF BELGESİ", ParagraphStyle("th",
        fontSize=14, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#333333"), spaceAfter=8)))

    tarih = datetime.now().strftime("%d/%m/%Y %H:%M")
    bilgiler = [
        ["Tarih:", tarih],
        ["Müşteri:", musteri],
        ["Ürün / Hizmet:", urun],
        ["Açıklama:", aciklama or "-"],
    ]
    bt = Table(bilgiler, colWidths=[4*cm, doc.width-4*cm])
    bt.setStyle(TableStyle([
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),
        ("FONTNAME",(1,0),(1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),10),
        ("TEXTCOLOR",(0,0),(0,-1),colors.HexColor("#8B4513")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.HexColor("#FFF8F0"),colors.white]),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),
    ]))
    els.append(bt)
    els.append(Spacer(1, 0.8*cm))

    kdv    = round(fiyat * KDV, 2)
    toplam = round(fiyat + kdv, 2)
    fveri  = [
        ["Açıklama", "Tutar"],
        ["Ürün / Hizmet Bedeli", f"{fiyat:,.2f} TL"],
        [f"KDV (%{int(KDV*100)})", f"{kdv:,.2f} TL"],
        ["TOPLAM (KDV Dahil)", f"{toplam:,.2f} TL"],
    ]
    ft = Table(fveri, colWidths=[doc.width*0.6, doc.width*0.4])
    ft.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#8B4513")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),10),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#FFF0E0")),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",(0,-1),(-1,-1),colors.HexColor("#8B4513")),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.HexColor("#FAFAFA"),colors.white]),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#D2691E")),
        ("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),8),
        ("LEFTPADDING",(0,0),(-1,-1),10),
        ("RIGHTPADDING",(0,0),(-1,-1),10),
    ]))
    els.append(ft)
    els.append(Spacer(1, 1*cm))
    els.append(Paragraph(
        "Bu teklif düzenlenme tarihinden itibaren 30 gün geçerlidir. Bilgi için lütfen iletişime geçiniz.",
        note_s))

    doc.build(els)
    buf.seek(0)
    return buf.read()


# ─── Veri Yönetimi ───────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def veri_yukle():
    try:
        return pd.read_csv(DATA_FILE)
    except Exception:
        return pd.DataFrame(columns=["Tarih","Müşteri","Ürün","Fiyat (KDV Hariç)","Açıklama"])

def veri_kaydet(df):
    df.to_csv(DATA_FILE, index=False)
    st.cache_data.clear()

def kart(label, value):
    return f'<div class="result-card"><div class="label">{label}</div><div class="value">{value}</div></div>'

# ─── Başlık ──────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image("logo.png", width=120)
with col_title:
    st.markdown("""
    <div class="main-header">
        <p style="font-size:1.6rem; font-weight:bold; letter-spacing:2px; margin:0; color:#FFF8DC;">GÜNEŞ AHŞAP AMBALAJ</p>
        <p style="margin:4px 0 0; color:#FFE4B5; font-size:0.95rem;">Hesaplama &amp; Teklif Yönetim Sistemi</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 📋 Modül Seç")
    menu = st.selectbox("", ["🪵 Kafes Sandık","📦 Palet","📄 Teklif Oluştur","📊 Teklif Listesi","⚙️ Malzeme Fiyatları"],
                        label_visibility="collapsed")
    st.markdown("---")
    st.markdown(f"**KDV:** %{int(KDV*100)} | **İşçilik:** %{int(ISCILIK_ARTIS*100)}")
    st.markdown(f"**Tarih:** {datetime.now().strftime('%d/%m/%Y')}")

# ─── Kafes Sandık ─────────────────────────────────────────────────────────────
if menu == "🪵 Kafes Sandık":
    st.markdown("### 🪵 Kafes Ahşap Sandık Hesaplama")
    st.caption("Formüller: HESAPLAMA.xlsm → KAFES_AHŞAP_SANDIK + KATLANIR sayfası")

    c1, c2 = st.columns(2)
    with c1:
        boy = st.number_input("Boy (cm)", min_value=0.0, step=1.0, format="%.0f")
        en  = st.number_input("En (cm)",  min_value=0.0, step=1.0, format="%.0f")
    with c2:
        yuk  = st.number_input("Yükseklik (cm)", min_value=0.0, step=1.0, format="%.0f")
        adet = st.number_input("Adet", min_value=1, step=1, value=1)

    with st.expander("🔧 Gelişmiş Ayarlar"):
        kalinlik = st.selectbox("Kontrplak Kalınlığı (mm)", [0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0], index=0)
        kapak_ad = st.number_input("Kapak Adedi", min_value=1, max_value=4, value=2)

    if st.button("🔢 Hesapla", key="sandik"):
        if boy == 0 or en == 0 or yuk == 0:
            st.warning("⚠️ Lütfen tüm ölçüleri girin.")
        else:
            s = kafes_sandik_hesapla(boy, en, yuk, adet, kalinlik, kapak_ad)
            st.markdown("---")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown(kart("Birim Satış Fiyatı", f"{s['birim_fiyat']:,.2f} ₺"), unsafe_allow_html=True)
            with r2:
                st.markdown(kart(f"Toplam ({adet} adet, KDV Hariç)", f"{s['toplam']:,.2f} ₺"), unsafe_allow_html=True)
            with r3:
                st.markdown(kart("KDV Dahil Toplam", f"{s['kdv_dahil']:,.2f} ₺"), unsafe_allow_html=True)
            with st.expander("📋 Detaylı Hesap"):
                st.write(f"- Ahşap Miktarı (toplam): **{s['ahsap_m3']:.6f} m³**")
                st.write(f"- Ahşap Birim Fiyatı: **{AHSAP_TL:,} ₺/m³**")
                st.write(f"- Malzeme Maliyeti: **{s['maliyet']:,.2f} ₺**")
                st.write(f"- İşçilik Artışı (%{int(ISCILIK_ARTIS*100)}): **{s['maliyet']*ISCILIK_ARTIS:,.2f} ₺**")
                st.write(f"- KDV Tutarı (%{int(KDV*100)}): **{s['kdv_tutari']:,.2f} ₺**")

# ─── Palet ────────────────────────────────────────────────────────────────────
elif menu == "📦 Palet":
    st.markdown("### 📦 Palet Hesaplama")
    st.caption("Formüller: HESAPLAMA.xlsm → PALET sayfası (Kadraj 10×10 Tam Kapalı)")

    c1, c2 = st.columns(2)
    with c1:
        boy = st.number_input("Boy (cm)", min_value=0.0, step=1.0, format="%.0f")
        en  = st.number_input("En (cm)",  min_value=0.0, step=1.0, format="%.0f")
    with c2:
        yuk  = st.number_input("Yükseklik (cm)", min_value=0.0, step=1.0, format="%.0f")
        adet = st.number_input("Adet", min_value=1, step=1, value=1)

    if st.button("🔢 Hesapla", key="palet"):
        if boy == 0 or en == 0:
            st.warning("⚠️ Lütfen en ve boy ölçülerini girin.")
        else:
            p = palet_hesapla(boy, en, yuk, adet)
            st.markdown("---")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown(kart("Birim Fiyat", f"{p['birim_fiyat']:,.2f} ₺"), unsafe_allow_html=True)
            with r2:
                st.markdown(kart(f"Toplam ({adet} adet, KDV Hariç)", f"{p['toplam']:,.2f} ₺"), unsafe_allow_html=True)
            with r3:
                st.markdown(kart("KDV Dahil Toplam", f"{p['kdv_dahil']:,.2f} ₺"), unsafe_allow_html=True)
            with st.expander("📋 Detaylı Hesap"):
                st.write(f"- Ahşap Miktarı (birim): **{p['ahsap_m3']:.6f} m³**")
                st.write(f"- Ahşap Birim Fiyatı: **{AHSAP_TL:,} ₺/m³**")
                st.write(f"- Malzeme Maliyeti: **{p['maliyet']:,.2f} ₺**")
                st.write(f"- İşçilik Artışı (%{int(ISCILIK_ARTIS*100)}): **{p['maliyet']*ISCILIK_ARTIS:,.2f} ₺**")
                st.write(f"- KDV Tutarı (%{int(KDV*100)}): **{p['kdv_tutari']:,.2f} ₺**")

# ─── Teklif Oluştur ────────────────────────────────────────────────────────────
elif menu == "📄 Teklif Oluştur":
    st.markdown("### 📄 Teklif Oluştur")
    c1, c2 = st.columns(2)
    with c1:
        musteri  = st.text_input("Müşteri Adı / Firma")
        urun     = st.text_input("Ürün / Hizmet Adı")
    with c2:
        fiyat    = st.number_input("Fiyat (KDV Hariç, ₺)", min_value=0.0, step=100.0, format="%.2f")
        aciklama = st.text_input("Açıklama (isteğe bağlı)")
    if fiyat > 0:
        kdv_g = round(fiyat * KDV, 2)
        st.info(f"KDV (%{int(KDV*100)}): **{kdv_g:,.2f} ₺** | KDV Dahil Toplam: **{fiyat+kdv_g:,.2f} ₺**")

    ca, cb = st.columns(2)
    with ca:
        if st.button("💾 Kaydet"):
            if not musteri or not urun or fiyat == 0:
                st.error("❌ Müşteri adı, ürün ve fiyat zorunludur.")
            else:
                df = veri_yukle()
                yeni = pd.DataFrame([{"Tarih": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                      "Müşteri": musteri, "Ürün": urun,
                                      "Fiyat (KDV Hariç)": fiyat, "Açıklama": aciklama}])
                df = pd.concat([df, yeni], ignore_index=True)
                veri_kaydet(df)
                st.success("✅ Teklif kaydedildi!")
    with cb:
        if st.button("📥 PDF Oluştur & İndir"):
            if not musteri or not urun or fiyat == 0:
                st.error("❌ Müşteri adı, ürün ve fiyat zorunludur.")
            else:
                pdf_bytes = teklif_pdf_olustur(musteri, urun, fiyat, aciklama)
                dosya_adi = f"teklif_{musteri.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
                st.download_button("⬇️ PDF İndir", data=pdf_bytes,
                                   file_name=dosya_adi, mime="application/pdf")

# ─── Teklif Listesi ────────────────────────────────────────────────────────────
elif menu == "📊 Teklif Listesi":
    st.markdown("### 📊 Teklif Listesi")
    df = veri_yukle()
    if df.empty:
        st.info("📭 Henüz kayıtlı teklif bulunmuyor.")
    else:
        toplam_tutar = df["Fiyat (KDV Hariç)"].sum() if "Fiyat (KDV Hariç)" in df.columns else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam Teklif", len(df))
        m2.metric("Toplam Tutar (KDV Hariç)", f"{toplam_tutar:,.2f} ₺")
        m3.metric("KDV Dahil Toplam", f"{toplam_tutar*(1+KDV):,.2f} ₺")
        st.markdown("---")
        ara = st.text_input("🔍 Müşteri veya ürün ara...")
        if ara:
            df = df[df.apply(lambda r: ara.lower() in str(r).lower(), axis=1)]
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ CSV İndir", data=csv, file_name="teklifler.csv", mime="text/csv")

# ─── Malzeme Fiyatları ─────────────────────────────────────────────────────────
elif menu == "⚙️ Malzeme Fiyatları":
    st.markdown("### ⚙️ Güncel Malzeme Fiyatları")
    st.info("Bu değerler HESAPLAMA.xlsm dosyasındaki SİPARİŞ sayfasından alınmıştır. Güncellemek için app.py'nin üst kısmındaki sabitleri değiştirin.")
    
    data = {
        "Malzeme": ["Kontrplak","Ahşap","Sac","Baskı","İp","Alü. Folyo","VCI Torba","Nem Alıcı"],
        "Birim":   ["₺/m³","₺/m³","₺/kg","₺/ad","₺/ad","₺/m²","₺/ad","₺/ad"],
        "Fiyat":   [KONTRPLAK_TL, AHSAP_TL, SAC_TL, BASKI_TL, IP_TL, ALU_FOLYO_TL, VCI_TORBA_TL, NEM_ALICI_TL],
        "Excel Hücre": ["SİPARİŞ!L4","SİPARİŞ!N4","SİPARİŞ!P4","SİPARİŞ!R4","SİPARİŞ!T4","SİPARİŞ!V4","SİPARİŞ!X4","SİPARİŞ!Z4"],
    }
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown(f"**İşçilik Artış Oranı:** %{int(ISCILIK_ARTIS*100)} (SİPARİŞ!AD11)")
    st.markdown(f"**KDV Oranı:** %{int(KDV*100)}")
