import requests
import json
from typing import List, Dict

# Kara liste ve yapılandırma dosyasını yükleme
CONFIG_FILE = "config.json"
RUGCHECK_API_URL = "http://rugcheck.xyz"
Rocker_API_URL = "https://rocker.universe/api"
TweetScout_API_URL = "http://app.tweetscout.io/api"

def load_config() -> Dict:
    """
    Yapılandırma dosyasını yükler.
    """
    try:
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        raise Exception(f"{CONFIG_FILE} dosyası bulunamadı.")
    except json.JSONDecodeError as e:
        raise Exception(f"Yapılandırma dosyası geçersiz: {e}")

def fetch_rugcheck_status(token_address: str) -> bool:
    """
    RugCheck API'sini kullanarak token sözleşmesini doğrular.
    """
    try:
        response = requests.get(f"{RUGCHECK_API_URL}/status/{token_address}", timeout=10)
        response.raise_for_status()
        result = response.json()
        return result.get("status") == "Good"
    except requests.exceptions.RequestException as e:
        print(f"RugCheck API hatası: {e}")
        return False

def verify_token_legitimacy(token_address: str) -> bool:
    """
    Rocker Universe API kullanarak token'ın sahte olup olmadığını doğrular.
    """
    try:
        response = requests.post(
            Rocker_API_URL + "/verify",
            json={"token_address": token_address},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result.get("is_legitimate", False)
    except requests.exceptions.RequestException as e:
        print(f"Rocker Universe API hatası: {e}")
        return False

def fetch_tweetscout_score(token_name: str) -> str:
    """
    TweetScout API kullanarak token için sosyal medya puanını alır.
    """
    try:
        response = requests.get(f"{TweetScout_API_URL}/score", params={"token_name": token_name}, timeout=10)
        response.raise_for_status()
        result = response.json()
        score = result.get("score", 0)
        if score > 450:
            return "Good"
        return "Average"
    except requests.exceptions.RequestException as e:
        print(f"TweetScout API hatası: {e}")
        return "Unknown"

def check_wrapped_supply(token_data: Dict) -> bool:
    """
    Token'ın tedarikinin paketlenmiş olup olmadığını kontrol eder.
    """
    supply_info = token_data.get("supply_info", {})
    return not supply_info.get("is_wrapped", False)

def filter_tokens_with_rugcheck(tokens: List[Dict], config: Dict) -> List[Dict]:
    """
    RugCheck, TweetScout ve diğer kriterlere göre tokenları filtreler.
    """
    filtered_tokens = []
    blacklist = set(config.get("blacklist", []))
    dev_blacklist = set(config.get("dev_blacklist", []))

    for token in tokens:
        developer = token.get("developer", "")
        token_address = token.get("address", "")

        # Kara liste kontrolü
        if developer in dev_blacklist or token_address in blacklist:
            print(f"{token['name']} kara listede, atlanıyor.")
            continue

        # RugCheck doğrulaması
        if not fetch_rugcheck_status(token_address):
            print(f"{token['name']} RugCheck'te 'İyi' olarak işaretlenmemiş, atlanıyor.")
            blacklist.add(token_address)
            continue

        # Tedarik doğrulaması
        if not check_wrapped_supply(token):
            print(f"{token['name']} paketlenmiş tedarike sahip, kara listeye ekleniyor.")
            blacklist.add(token_address)
            continue

        # TweetScout doğrulaması
        tweet_score = fetch_tweetscout_score(token.get("name", ""))
        if tweet_score != "Good":
            print(f"{token['name']} sosyal medya skoru yeterli değil ({tweet_score}), atlanıyor.")
            continue

        # Diğer filtre kriterleri
        if token.get("age", 0) <= config.get("max_age", 24) and \
           token.get("1h_txns", 0) >= config.get("min_1h_txns", 150) and \
           token.get("5m_txns", 0) >= config.get("min_5m_txns", 25):
            filtered_tokens.append(token)

    # Güncellenmiş kara listeyi yapılandırma dosyasına kaydet
    config["blacklist"] = list(blacklist)
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)

    return filtered_tokens

def fetch_and_process_data():
    """
    Verileri çeker, filtreler ve analiz eder.
    """
    try:
        # Yapılandırmayı yükle
        config = load_config()

        # 1. Pump.fun'dan veri çek
        pump_data = fetch_pumpfun_data()
        print("PumpFun verileri başarıyla alındı.")

        # 2. Tokenları RugCheck, TweetScout ve diğer kriterlere göre filtrele
        tokens = pump_data.get("tokens", [])
        if not tokens:
            print("PumpFun'dan gelen token verisi boş.")
            return

        filtered_tokens = filter_tokens_with_rugcheck(tokens, config)
        print(f"Filtrelenmiş token sayısı: {len(filtered_tokens)}")

        # 3. Sahte hacim kontrolü ve analiz
        for token in filtered_tokens:
            if not verify_token_legitimacy(token["address"]):
                print(f"{token['name']} (Adres: {token['address']}) sahte hacim şüphesi nedeniyle atlandı.")
                continue

            print(f"Token: {token['name']} - RugCheck, TweetScout ve tedarik doğrulandı.")

    except Exception as e:
        print(f"Hata: {e}")

def main():
    """
    Ana çalışma fonksiyonu.
    """
    print("Veri işleme başlatılıyor...")
    fetch_and_process_data()
    print("Veri işleme tamamlandı.")

if __name__ == "__main__":
    main()
