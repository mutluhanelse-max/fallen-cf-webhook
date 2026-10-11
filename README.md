# FallenSkullCorp CurseForge -> Discord

Her 30 dakikada bir addonları kontrol eder, yeni dosya yüklendiyse Discord'a duyuru atar.

## Kurulum
1. GitHub'da yeni bir repo aç (private olabilir) ve bu klasördeki dosyaları yükle.
2. Repo > Settings > Secrets and variables > Actions > **New repository secret**:
   - `DISCORD_WEBHOOK_URL` = Discord webhook adresi
   - (isteğe bağlı) `CF_API_KEY` = https://console.curseforge.com adresinden alınan API anahtarı. Varsa duyuruya changelog metni de eklenir.
3. (isteğe bağlı) Variables sekmesinde `DISCORD_ROLE_ID`: duyuruda etiketlenecek rolün ID'si.
4. Actions sekmesi > "CurseForge -> Discord" > **Run workflow**. İlk çalışma sadece mevcut sürümleri kaydeder, duyuru atmaz.

Yeni addon yayına çıkınca adresinin son kısmını `addons.json` listesine ekle.
