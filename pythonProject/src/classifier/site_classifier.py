import logging
from google import genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = genai.Client(api_key="AIzaSyA4yIeLORLv-8deYL_P_qDZDLtM8ZEh3fE")

site_types = [
    "E-ticaret", "Haber", "Kurumsal", "Blog", "Sosyal",
    "Eğitim", "Forum", "Sağlık", "Hizmet", "Oyun"
]

def classify_site(site_content):
    logger.info("Site içeriği sınıflandırma işlemi başladı.")

    prompt = f"""
    Aşağıdaki web sitesi içeriğini analiz et ve en uygun kategoriyi belirle.
    Kategoriler: {', '.join(site_types)}
    İçerik: {site_content}

    Sadece en uygun kategoriyi döndür.
    """

    logger.info(f"Oluşturulan prompt: {prompt}")

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash", contents=prompt
        )
        category = response.text.strip()

        logger.info(f"Sınıflandırma tamamlandı. Sonuç: {category}")
        return category
    except Exception as e:
        logger.error(f"Hata oluştu: {e}")
        return "Bilinmeyen"
