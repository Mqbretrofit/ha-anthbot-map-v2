/* ANTHBOT Map developer opt-in popup.
 * Loaded as a separate Lovelace resource. It follows the current Home Assistant
 * user-interface language automatically; unsupported languages fall back to English.
 */

const ANTHBOT_OPTIN_SUPPORTED = new Set([
  "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk", "ro",
  "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi", "ko", "km",
]);

const ANTHBOT_OPTIN_TEXT = {
  en:{title:"Would you like to help develop ANTHBOT Map?",subtitle:"By optionally sharing usage statistics and diagnostic data, you can help us fix issues faster and improve support for different ANTHBOT models.",usageTitle:"Share usage statistics",usageDesc:"Minimal technical data such as integration version, Home Assistant version, country and the number of ANTHBOT models in use. Username, password, serial number, GPS position and map are not sent.",diagTitle:"Send automatic diagnostic reports",diagDesc:"If an error occurs, privacy-filtered technical diagnostics may be sent to help development. This does not change or control the robot.",privacy:"Data sharing is completely optional and can be turned off at any time.",privacyLink:"Privacy notice",later:"Not now",save:"Save settings",saving:"Saving…",thanks:"Thank you for helping!",saved:"Settings saved",thanksDesc:"Your choice was saved. Because you enabled at least one option, this popup will not appear again after future integration updates.",declinedDesc:"Nothing was enabled. This popup is hidden for this version and may be offered again after a future integration update.",done:"OK",error:"Could not save the setting. Please try again."},
  hu:{title:"Segítenél az ANTHBOT Map fejlesztésében?",subtitle:"Az opcionális használati statisztikák és diagnosztikai adatok megosztásával segíthetsz a hibák gyorsabb javításában és a különböző ANTHBOT modellek jobb támogatásában.",usageTitle:"Használati statisztikák megosztása",usageDesc:"Minimális technikai adatok, például integrációverzió, Home Assistant verzió, ország és a használt ANTHBOT modellek száma. Felhasználónév, jelszó, sorozatszám, GPS-pozíció és térkép nem kerül elküldésre.",diagTitle:"Automatikus diagnosztikai jelentések küldése",diagDesc:"Hiba esetén adatvédelmi szűrésen átesett technikai diagnosztika küldhető a fejlesztés segítésére. Ez nem módosítja és nem vezérli a robotot.",privacy:"Az adatküldés teljesen önkéntes, és bármikor kikapcsolható.",privacyLink:"Adatvédelmi tájékoztató",later:"Most nem",save:"Beállítások mentése",saving:"Mentés…",thanks:"Köszönjük a segítséget!",saved:"Beállítások elmentve",thanksDesc:"A választásod elmentettük. Mivel legalább egy lehetőséget engedélyeztél, ez a popup a későbbi integrációfrissítéseknél már nem jelenik meg.",declinedDesc:"Nem engedélyeztél adatküldést. Ennél a verziónál a popup nem jelenik meg újra, egy későbbi integrációfrissítésnél viszont ismét felajánlhatjuk.",done:"Rendben",error:"A beállítás mentése nem sikerült. Próbáld újra."},
  de:{title:"Möchtest du die Entwicklung von ANTHBOT Map unterstützen?",subtitle:"Durch die freiwillige Freigabe von Nutzungsstatistiken und Diagnosedaten hilfst du uns, Fehler schneller zu beheben und verschiedene ANTHBOT-Modelle besser zu unterstützen.",usageTitle:"Nutzungsstatistiken teilen",usageDesc:"Minimale technische Daten wie Integrationsversion, Home-Assistant-Version, Land und Anzahl der verwendeten ANTHBOT-Modelle. Benutzername, Passwort, Seriennummer, GPS-Position und Karte werden nicht gesendet.",diagTitle:"Automatische Diagnoseberichte senden",diagDesc:"Bei einem Fehler können datenschutzgefilterte technische Diagnosedaten zur Unterstützung der Entwicklung gesendet werden. Dadurch wird der Roboter weder verändert noch gesteuert.",privacy:"Die Datenfreigabe ist vollständig freiwillig und kann jederzeit deaktiviert werden.",privacyLink:"Datenschutzhinweis",later:"Jetzt nicht",save:"Einstellungen speichern",saving:"Speichern…",thanks:"Danke für deine Unterstützung!",saved:"Einstellungen gespeichert",thanksDesc:"Deine Auswahl wurde gespeichert. Da mindestens eine Option aktiviert wurde, erscheint dieses Fenster bei zukünftigen Updates nicht mehr.",declinedDesc:"Es wurde nichts aktiviert. Für diese Version bleibt das Fenster verborgen und kann nach einem späteren Update erneut angeboten werden.",done:"OK",error:"Die Einstellung konnte nicht gespeichert werden. Bitte erneut versuchen."},
  fr:{title:"Souhaitez-vous aider au développement d’ANTHBOT Map ?",subtitle:"En partageant facultativement des statistiques d’utilisation et des données de diagnostic, vous pouvez nous aider à corriger les problèmes plus vite et à mieux prendre en charge les différents modèles ANTHBOT.",usageTitle:"Partager les statistiques d’utilisation",usageDesc:"Données techniques minimales comme la version de l’intégration, la version de Home Assistant, le pays et le nombre de modèles ANTHBOT utilisés. Le nom d’utilisateur, le mot de passe, le numéro de série, la position GPS et la carte ne sont pas envoyés.",diagTitle:"Envoyer automatiquement des rapports de diagnostic",diagDesc:"En cas d’erreur, des diagnostics techniques filtrés pour la confidentialité peuvent être envoyés afin d’aider au développement. Cela ne modifie ni ne contrôle le robot.",privacy:"Le partage des données est entièrement facultatif et peut être désactivé à tout moment.",privacyLink:"Avis de confidentialité",later:"Pas maintenant",save:"Enregistrer",saving:"Enregistrement…",thanks:"Merci pour votre aide !",saved:"Paramètres enregistrés",thanksDesc:"Votre choix a été enregistré. Au moins une option étant activée, cette fenêtre ne réapparaîtra plus lors des prochaines mises à jour.",declinedDesc:"Aucune option n’a été activée. Cette fenêtre reste masquée pour cette version et pourra être reproposée après une future mise à jour.",done:"OK",error:"Impossible d’enregistrer le réglage. Veuillez réessayer."},
  es:{title:"¿Quieres ayudar a desarrollar ANTHBOT Map?",subtitle:"Al compartir de forma opcional estadísticas de uso y datos de diagnóstico, puedes ayudarnos a corregir problemas más rápido y mejorar la compatibilidad con distintos modelos ANTHBOT.",usageTitle:"Compartir estadísticas de uso",usageDesc:"Datos técnicos mínimos como la versión de la integración, la versión de Home Assistant, el país y el número de modelos ANTHBOT utilizados. No se envían nombre de usuario, contraseña, número de serie, posición GPS ni mapa.",diagTitle:"Enviar informes de diagnóstico automáticos",diagDesc:"Si se produce un error, pueden enviarse diagnósticos técnicos filtrados para proteger la privacidad y ayudar al desarrollo. Esto no modifica ni controla el robot.",privacy:"El envío de datos es totalmente opcional y puede desactivarse en cualquier momento.",privacyLink:"Aviso de privacidad",later:"Ahora no",save:"Guardar ajustes",saving:"Guardando…",thanks:"¡Gracias por ayudar!",saved:"Ajustes guardados",thanksDesc:"Tu elección se ha guardado. Como activaste al menos una opción, esta ventana no volverá a aparecer tras futuras actualizaciones.",declinedDesc:"No se activó ninguna opción. La ventana queda oculta para esta versión y podrá ofrecerse de nuevo tras una futura actualización.",done:"Aceptar",error:"No se pudo guardar el ajuste. Inténtalo de nuevo."},
  it:{title:"Vuoi aiutare lo sviluppo di ANTHBOT Map?",subtitle:"Condividendo facoltativamente statistiche di utilizzo e dati diagnostici puoi aiutarci a correggere più rapidamente i problemi e a migliorare il supporto ai diversi modelli ANTHBOT.",usageTitle:"Condividi statistiche di utilizzo",usageDesc:"Dati tecnici minimi come versione dell’integrazione, versione di Home Assistant, paese e numero di modelli ANTHBOT utilizzati. Nome utente, password, numero di serie, posizione GPS e mappa non vengono inviati.",diagTitle:"Invia automaticamente rapporti diagnostici",diagDesc:"In caso di errore possono essere inviati dati diagnostici tecnici filtrati per la privacy per aiutare lo sviluppo. Questo non modifica né controlla il robot.",privacy:"La condivisione dei dati è completamente facoltativa e può essere disattivata in qualsiasi momento.",privacyLink:"Informativa sulla privacy",later:"Non ora",save:"Salva impostazioni",saving:"Salvataggio…",thanks:"Grazie per il tuo aiuto!",saved:"Impostazioni salvate",thanksDesc:"La scelta è stata salvata. Poiché hai attivato almeno un’opzione, questa finestra non apparirà più dopo i futuri aggiornamenti.",declinedDesc:"Non è stata attivata alcuna opzione. La finestra resta nascosta per questa versione e potrà essere riproposta dopo un futuro aggiornamento.",done:"OK",error:"Impossibile salvare l’impostazione. Riprova."},
  pt:{title:"Gostaria de ajudar no desenvolvimento do ANTHBOT Map?",subtitle:"Ao partilhar opcionalmente estatísticas de utilização e dados de diagnóstico, pode ajudar-nos a corrigir problemas mais rapidamente e a melhorar o suporte para diferentes modelos ANTHBOT.",usageTitle:"Partilhar estatísticas de utilização",usageDesc:"Dados técnicos mínimos, como versão da integração, versão do Home Assistant, país e número de modelos ANTHBOT utilizados. Nome de utilizador, palavra-passe, número de série, posição GPS e mapa não são enviados.",diagTitle:"Enviar relatórios de diagnóstico automáticos",diagDesc:"Se ocorrer um erro, poderão ser enviados diagnósticos técnicos filtrados para privacidade para ajudar no desenvolvimento. Isto não altera nem controla o robô.",privacy:"A partilha de dados é totalmente opcional e pode ser desativada a qualquer momento.",privacyLink:"Aviso de privacidade",later:"Agora não",save:"Guardar definições",saving:"A guardar…",thanks:"Obrigado pela ajuda!",saved:"Definições guardadas",thanksDesc:"A sua escolha foi guardada. Como ativou pelo menos uma opção, esta janela não voltará a aparecer após futuras atualizações.",declinedDesc:"Nenhuma opção foi ativada. A janela fica oculta nesta versão e poderá ser apresentada novamente após uma futura atualização.",done:"OK",error:"Não foi possível guardar a definição. Tente novamente."},
  nl:{title:"Wil je helpen met de ontwikkeling van ANTHBOT Map?",subtitle:"Door optioneel gebruiksstatistieken en diagnostische gegevens te delen, help je ons problemen sneller op te lossen en ondersteuning voor verschillende ANTHBOT-modellen te verbeteren.",usageTitle:"Gebruiksstatistieken delen",usageDesc:"Minimale technische gegevens zoals integratieversie, Home Assistant-versie, land en het aantal gebruikte ANTHBOT-modellen. Gebruikersnaam, wachtwoord, serienummer, GPS-positie en kaart worden niet verzonden.",diagTitle:"Automatische diagnoserapporten verzenden",diagDesc:"Bij een fout kunnen privacy-gefilterde technische diagnosegegevens worden verzonden om de ontwikkeling te helpen. Dit wijzigt of bestuurt de robot niet.",privacy:"Gegevens delen is volledig optioneel en kan op elk moment worden uitgeschakeld.",privacyLink:"Privacyverklaring",later:"Niet nu",save:"Instellingen opslaan",saving:"Opslaan…",thanks:"Bedankt voor je hulp!",saved:"Instellingen opgeslagen",thanksDesc:"Je keuze is opgeslagen. Omdat minstens één optie is ingeschakeld, verschijnt dit venster na toekomstige updates niet meer.",declinedDesc:"Er is niets ingeschakeld. Het venster blijft voor deze versie verborgen en kan na een toekomstige update opnieuw worden aangeboden.",done:"OK",error:"De instelling kon niet worden opgeslagen. Probeer het opnieuw."},
  pl:{title:"Czy chcesz pomóc w rozwoju ANTHBOT Map?",subtitle:"Opcjonalne udostępnianie statystyk użycia i danych diagnostycznych pomoże nam szybciej usuwać błędy i lepiej wspierać różne modele ANTHBOT.",usageTitle:"Udostępniaj statystyki użycia",usageDesc:"Minimalne dane techniczne, takie jak wersja integracji, wersja Home Assistant, kraj i liczba używanych modeli ANTHBOT. Nazwa użytkownika, hasło, numer seryjny, pozycja GPS i mapa nie są wysyłane.",diagTitle:"Wysyłaj automatyczne raporty diagnostyczne",diagDesc:"W przypadku błędu mogą zostać wysłane dane diagnostyczne przefiltrowane pod kątem prywatności, aby pomóc w rozwoju. Nie zmienia to ani nie steruje robotem.",privacy:"Udostępnianie danych jest całkowicie dobrowolne i można je wyłączyć w dowolnym momencie.",privacyLink:"Informacja o prywatności",later:"Nie teraz",save:"Zapisz ustawienia",saving:"Zapisywanie…",thanks:"Dziękujemy za pomoc!",saved:"Ustawienia zapisane",thanksDesc:"Wybór został zapisany. Ponieważ włączono co najmniej jedną opcję, okno nie pojawi się ponownie po przyszłych aktualizacjach.",declinedDesc:"Nie włączono żadnej opcji. Okno jest ukryte dla tej wersji i może zostać pokazane po przyszłej aktualizacji.",done:"OK",error:"Nie udało się zapisać ustawienia. Spróbuj ponownie."},
  cs:{title:"Chcete pomoci s vývojem ANTHBOT Map?",subtitle:"Volitelným sdílením statistik používání a diagnostických dat nám můžete pomoci rychleji opravovat chyby a zlepšovat podporu různých modelů ANTHBOT.",usageTitle:"Sdílet statistiky používání",usageDesc:"Minimální technické údaje, například verze integrace, verze Home Assistant, země a počet používaných modelů ANTHBOT. Uživatelské jméno, heslo, sériové číslo, poloha GPS ani mapa se neodesílají.",diagTitle:"Odesílat automatické diagnostické zprávy",diagDesc:"Při chybě mohou být odeslána technická diagnostická data filtrovaná z hlediska soukromí, aby pomohla vývoji. Robot se tím nemění ani neovládá.",privacy:"Sdílení dat je zcela dobrovolné a lze je kdykoli vypnout.",privacyLink:"Informace o soukromí",later:"Teď ne",save:"Uložit nastavení",saving:"Ukládání…",thanks:"Děkujeme za pomoc!",saved:"Nastavení uloženo",thanksDesc:"Vaše volba byla uložena. Protože je zapnutá alespoň jedna možnost, toto okno se po budoucích aktualizacích již nezobrazí.",declinedDesc:"Nebyla zapnuta žádná možnost. Okno je pro tuto verzi skryté a může být znovu nabídnuto po budoucí aktualizaci.",done:"OK",error:"Nastavení se nepodařilo uložit. Zkuste to znovu."},
  sk:{title:"Chcete pomôcť s vývojom ANTHBOT Map?",subtitle:"Voliteľným zdieľaním štatistík používania a diagnostických údajov nám môžete pomôcť rýchlejšie opravovať chyby a zlepšovať podporu rôznych modelov ANTHBOT.",usageTitle:"Zdieľať štatistiky používania",usageDesc:"Minimálne technické údaje, napríklad verzia integrácie, verzia Home Assistant, krajina a počet používaných modelov ANTHBOT. Používateľské meno, heslo, sériové číslo, poloha GPS ani mapa sa neposielajú.",diagTitle:"Odosielať automatické diagnostické správy",diagDesc:"Pri chybe môžu byť odoslané technické diagnostické údaje filtrované z hľadiska súkromia, aby pomohli vývoju. Robot sa tým nemení ani neovláda.",privacy:"Zdieľanie údajov je úplne dobrovoľné a možno ho kedykoľvek vypnúť.",privacyLink:"Informácie o súkromí",later:"Teraz nie",save:"Uložiť nastavenia",saving:"Ukladanie…",thanks:"Ďakujeme za pomoc!",saved:"Nastavenia uložené",thanksDesc:"Vaša voľba bola uložená. Keďže je zapnutá aspoň jedna možnosť, toto okno sa po budúcich aktualizáciách už nezobrazí.",declinedDesc:"Nebola zapnutá žiadna možnosť. Okno je pre túto verziu skryté a môže sa znovu ponúknuť po budúcej aktualizácii.",done:"OK",error:"Nastavenie sa nepodarilo uložiť. Skúste to znova."},
  ro:{title:"Doriți să ajutați la dezvoltarea ANTHBOT Map?",subtitle:"Prin partajarea opțională a statisticilor de utilizare și a datelor de diagnostic, ne puteți ajuta să remediem mai repede problemele și să îmbunătățim suportul pentru diferite modele ANTHBOT.",usageTitle:"Partajează statistici de utilizare",usageDesc:"Date tehnice minime, precum versiunea integrării, versiunea Home Assistant, țara și numărul de modele ANTHBOT utilizate. Numele de utilizator, parola, numărul de serie, poziția GPS și harta nu sunt trimise.",diagTitle:"Trimite automat rapoarte de diagnostic",diagDesc:"Dacă apare o eroare, pot fi trimise diagnostice tehnice filtrate pentru confidențialitate pentru a ajuta dezvoltarea. Acest lucru nu modifică și nu controlează robotul.",privacy:"Partajarea datelor este complet opțională și poate fi dezactivată în orice moment.",privacyLink:"Notificare de confidențialitate",later:"Nu acum",save:"Salvează setările",saving:"Se salvează…",thanks:"Mulțumim pentru ajutor!",saved:"Setări salvate",thanksDesc:"Alegerea a fost salvată. Deoarece este activată cel puțin o opțiune, această fereastră nu va mai apărea după actualizările viitoare.",declinedDesc:"Nu a fost activată nicio opțiune. Fereastra rămâne ascunsă pentru această versiune și poate fi oferită din nou după o actualizare viitoare.",done:"OK",error:"Setarea nu a putut fi salvată. Încercați din nou."},
  da:{title:"Vil du hjælpe med udviklingen af ANTHBOT Map?",subtitle:"Ved frivilligt at dele brugsstatistik og diagnostikdata kan du hjælpe os med at rette fejl hurtigere og forbedre understøttelsen af forskellige ANTHBOT-modeller.",usageTitle:"Del brugsstatistik",usageDesc:"Minimale tekniske data som integrationsversion, Home Assistant-version, land og antal anvendte ANTHBOT-modeller. Brugernavn, adgangskode, serienummer, GPS-position og kort sendes ikke.",diagTitle:"Send automatiske diagnoserapporter",diagDesc:"Hvis der opstår en fejl, kan privatlivsfiltrerede tekniske diagnosedata sendes for at hjælpe udviklingen. Det ændrer eller styrer ikke robotten.",privacy:"Datadeling er helt frivillig og kan slås fra når som helst.",privacyLink:"Privatlivsmeddelelse",later:"Ikke nu",save:"Gem indstillinger",saving:"Gemmer…",thanks:"Tak for hjælpen!",saved:"Indstillinger gemt",thanksDesc:"Dit valg er gemt. Da mindst én mulighed er aktiveret, vises vinduet ikke igen efter fremtidige opdateringer.",declinedDesc:"Ingen muligheder blev aktiveret. Vinduet er skjult for denne version og kan tilbydes igen efter en fremtidig opdatering.",done:"OK",error:"Indstillingen kunne ikke gemmes. Prøv igen."},
  sv:{title:"Vill du hjälpa till med utvecklingen av ANTHBOT Map?",subtitle:"Genom att frivilligt dela användningsstatistik och diagnostikdata kan du hjälpa oss att åtgärda problem snabbare och förbättra stödet för olika ANTHBOT-modeller.",usageTitle:"Dela användningsstatistik",usageDesc:"Minimala tekniska data som integrationsversion, Home Assistant-version, land och antal använda ANTHBOT-modeller. Användarnamn, lösenord, serienummer, GPS-position och karta skickas inte.",diagTitle:"Skicka automatiska diagnostikrapporter",diagDesc:"Om ett fel uppstår kan sekretessfiltrerad teknisk diagnostik skickas för att hjälpa utvecklingen. Detta ändrar eller styr inte roboten.",privacy:"Datadelning är helt frivillig och kan stängas av när som helst.",privacyLink:"Integritetsmeddelande",later:"Inte nu",save:"Spara inställningar",saving:"Sparar…",thanks:"Tack för hjälpen!",saved:"Inställningar sparade",thanksDesc:"Ditt val har sparats. Eftersom minst ett alternativ är aktiverat visas fönstret inte igen efter framtida uppdateringar.",declinedDesc:"Inget alternativ aktiverades. Fönstret är dolt för denna version och kan erbjudas igen efter en framtida uppdatering.",done:"OK",error:"Inställningen kunde inte sparas. Försök igen."},
  no:{title:"Vil du hjelpe med utviklingen av ANTHBOT Map?",subtitle:"Ved frivillig deling av bruksstatistikk og diagnosedata kan du hjelpe oss med å rette feil raskere og forbedre støtten for ulike ANTHBOT-modeller.",usageTitle:"Del bruksstatistikk",usageDesc:"Minimale tekniske data som integrasjonsversjon, Home Assistant-versjon, land og antall ANTHBOT-modeller i bruk. Brukernavn, passord, serienummer, GPS-posisjon og kart sendes ikke.",diagTitle:"Send automatiske diagnoserapporter",diagDesc:"Hvis det oppstår en feil, kan personvernfiltrert teknisk diagnostikk sendes for å hjelpe utviklingen. Dette endrer eller styrer ikke roboten.",privacy:"Datadeling er helt frivillig og kan slås av når som helst.",privacyLink:"Personvernerklæring",later:"Ikke nå",save:"Lagre innstillinger",saving:"Lagrer…",thanks:"Takk for hjelpen!",saved:"Innstillinger lagret",thanksDesc:"Valget ditt er lagret. Siden minst ett alternativ er aktivert, vises vinduet ikke igjen etter fremtidige oppdateringer.",declinedDesc:"Ingen alternativer ble aktivert. Vinduet er skjult for denne versjonen og kan tilbys igjen etter en fremtidig oppdatering.",done:"OK",error:"Innstillingen kunne ikke lagres. Prøv igjen."},
  fi:{title:"Haluatko auttaa ANTHBOT Mapin kehityksessä?",subtitle:"Jakamalla vapaaehtoisesti käyttötilastoja ja diagnostiikkatietoja voit auttaa meitä korjaamaan ongelmia nopeammin ja parantamaan eri ANTHBOT-mallien tukea.",usageTitle:"Jaa käyttötilastoja",usageDesc:"Vähäiset tekniset tiedot, kuten integraation versio, Home Assistant -versio, maa ja käytössä olevien ANTHBOT-mallien määrä. Käyttäjänimeä, salasanaa, sarjanumeroa, GPS-sijaintia tai karttaa ei lähetetä.",diagTitle:"Lähetä automaattisia diagnostiikkaraportteja",diagDesc:"Virheen ilmetessä voidaan lähettää yksityisyyden suojaamiseksi suodatettua teknistä diagnostiikkaa kehityksen tueksi. Tämä ei muuta eikä ohjaa robottia.",privacy:"Tietojen jakaminen on täysin vapaaehtoista ja sen voi poistaa käytöstä milloin tahansa.",privacyLink:"Tietosuojailmoitus",later:"Ei nyt",save:"Tallenna asetukset",saving:"Tallennetaan…",thanks:"Kiitos avusta!",saved:"Asetukset tallennettu",thanksDesc:"Valintasi tallennettiin. Koska vähintään yksi vaihtoehto on käytössä, ikkuna ei näy enää tulevien päivitysten jälkeen.",declinedDesc:"Mitään vaihtoehtoa ei otettu käyttöön. Ikkuna on piilotettu tässä versiossa ja voidaan tarjota uudelleen tulevan päivityksen jälkeen.",done:"OK",error:"Asetusta ei voitu tallentaa. Yritä uudelleen."},
  "zh-CN":{title:"愿意帮助改进 ANTHBOT Map 吗？",subtitle:"通过自愿分享使用统计和诊断数据，你可以帮助我们更快修复问题，并改进对不同 ANTHBOT 型号的支持。",usageTitle:"分享使用统计",usageDesc:"仅包含最少的技术数据，例如集成版本、Home Assistant 版本、国家/地区以及正在使用的 ANTHBOT 型号数量。不会发送用户名、密码、序列号、GPS 位置或地图。",diagTitle:"自动发送诊断报告",diagDesc:"发生错误时，可发送经过隐私过滤的技术诊断信息来帮助开发。这不会修改或控制机器人。",privacy:"数据分享完全自愿，可随时关闭。",privacyLink:"隐私说明",later:"暂不",save:"保存设置",saving:"正在保存…",thanks:"感谢你的帮助！",saved:"设置已保存",thanksDesc:"你的选择已保存。由于至少启用了一个选项，此窗口在后续更新后将不再显示。",declinedDesc:"未启用任何选项。此版本中窗口将保持隐藏，未来更新后可能再次询问。",done:"确定",error:"无法保存设置，请重试。"},
  "zh-TW":{title:"願意協助改進 ANTHBOT Map 嗎？",subtitle:"透過自願分享使用統計與診斷資料，你可以協助我們更快修正問題，並改善對不同 ANTHBOT 型號的支援。",usageTitle:"分享使用統計",usageDesc:"僅包含最少的技術資料，例如整合版本、Home Assistant 版本、國家/地區以及使用中的 ANTHBOT 型號數量。不會傳送使用者名稱、密碼、序號、GPS 位置或地圖。",diagTitle:"自動傳送診斷報告",diagDesc:"發生錯誤時，可傳送經過隱私篩選的技術診斷資訊以協助開發。這不會修改或控制機器人。",privacy:"資料分享完全自願，可隨時關閉。",privacyLink:"隱私權說明",later:"暫時不要",save:"儲存設定",saving:"儲存中…",thanks:"感謝你的協助！",saved:"設定已儲存",thanksDesc:"你的選擇已儲存。因為至少啟用了一個選項，此視窗在後續更新後將不再顯示。",declinedDesc:"沒有啟用任何選項。此版本中視窗將保持隱藏，未來更新後可能再次詢問。",done:"確定",error:"無法儲存設定，請再試一次。"},
  tr:{title:"ANTHBOT Map geliştirmesine yardımcı olmak ister misiniz?",subtitle:"İsteğe bağlı kullanım istatistikleri ve tanılama verileri paylaşarak sorunları daha hızlı düzeltmemize ve farklı ANTHBOT modellerinin desteğini geliştirmemize yardımcı olabilirsiniz.",usageTitle:"Kullanım istatistiklerini paylaş",usageDesc:"Entegrasyon sürümü, Home Assistant sürümü, ülke ve kullanılan ANTHBOT model sayısı gibi minimum teknik veriler. Kullanıcı adı, parola, seri numarası, GPS konumu ve harita gönderilmez.",diagTitle:"Otomatik tanılama raporları gönder",diagDesc:"Bir hata oluştuğunda, geliştirmeye yardımcı olmak için gizlilik filtresinden geçirilmiş teknik tanılama verileri gönderilebilir. Bu, robotu değiştirmez veya kontrol etmez.",privacy:"Veri paylaşımı tamamen isteğe bağlıdır ve istediğiniz zaman kapatılabilir.",privacyLink:"Gizlilik bildirimi",later:"Şimdi değil",save:"Ayarları kaydet",saving:"Kaydediliyor…",thanks:"Yardımınız için teşekkürler!",saved:"Ayarlar kaydedildi",thanksDesc:"Seçiminiz kaydedildi. En az bir seçenek etkin olduğu için bu pencere sonraki güncellemelerde tekrar görünmeyecek.",declinedDesc:"Hiçbir seçenek etkinleştirilmedi. Pencere bu sürüm için gizlenecek ve gelecekteki bir güncellemede tekrar sunulabilir.",done:"Tamam",error:"Ayar kaydedilemedi. Lütfen tekrar deneyin."},
  th:{title:"ต้องการช่วยพัฒนา ANTHBOT Map ไหม?",subtitle:"การแชร์สถิติการใช้งานและข้อมูลวินิจฉัยแบบสมัครใจจะช่วยให้เราแก้ปัญหาได้เร็วขึ้นและปรับปรุงการรองรับ ANTHBOT รุ่นต่าง ๆ",usageTitle:"แชร์สถิติการใช้งาน",usageDesc:"ข้อมูลทางเทคนิคขั้นต่ำ เช่น เวอร์ชันอินทิเกรชัน เวอร์ชัน Home Assistant ประเทศ และจำนวนรุ่น ANTHBOT ที่ใช้งาน จะไม่ส่งชื่อผู้ใช้ รหัสผ่าน หมายเลขซีเรียล ตำแหน่ง GPS หรือแผนที่",diagTitle:"ส่งรายงานวินิจฉัยอัตโนมัติ",diagDesc:"เมื่อเกิดข้อผิดพลาด อาจส่งข้อมูลวินิจฉัยทางเทคนิคที่ผ่านการกรองด้านความเป็นส่วนตัวเพื่อช่วยในการพัฒนา โดยจะไม่เปลี่ยนแปลงหรือควบคุมหุ่นยนต์",privacy:"การแชร์ข้อมูลเป็นทางเลือกทั้งหมดและปิดได้ทุกเมื่อ",privacyLink:"ประกาศความเป็นส่วนตัว",later:"ยังไม่ตอนนี้",save:"บันทึกการตั้งค่า",saving:"กำลังบันทึก…",thanks:"ขอบคุณที่ช่วยเหลือ!",saved:"บันทึกการตั้งค่าแล้ว",thanksDesc:"บันทึกตัวเลือกแล้ว เนื่องจากเปิดอย่างน้อยหนึ่งตัวเลือก หน้าต่างนี้จะไม่แสดงอีกในการอัปเดตครั้งต่อไป",declinedDesc:"ไม่ได้เปิดตัวเลือกใด หน้าต่างจะถูกซ่อนในเวอร์ชันนี้และอาจเสนออีกครั้งหลังการอัปเดตในอนาคต",done:"ตกลง",error:"ไม่สามารถบันทึกการตั้งค่าได้ โปรดลองอีกครั้ง"},
  vi:{title:"Bạn có muốn hỗ trợ phát triển ANTHBOT Map không?",subtitle:"Bằng cách tự nguyện chia sẻ thống kê sử dụng và dữ liệu chẩn đoán, bạn có thể giúp chúng tôi sửa lỗi nhanh hơn và cải thiện hỗ trợ cho các mẫu ANTHBOT khác nhau.",usageTitle:"Chia sẻ thống kê sử dụng",usageDesc:"Dữ liệu kỹ thuật tối thiểu như phiên bản tích hợp, phiên bản Home Assistant, quốc gia và số mẫu ANTHBOT đang sử dụng. Không gửi tên người dùng, mật khẩu, số sê-ri, vị trí GPS hay bản đồ.",diagTitle:"Tự động gửi báo cáo chẩn đoán",diagDesc:"Khi có lỗi, dữ liệu chẩn đoán kỹ thuật đã được lọc bảo vệ quyền riêng tư có thể được gửi để hỗ trợ phát triển. Việc này không thay đổi hoặc điều khiển robot.",privacy:"Việc chia sẻ dữ liệu hoàn toàn tự nguyện và có thể tắt bất cứ lúc nào.",privacyLink:"Thông báo quyền riêng tư",later:"Không phải bây giờ",save:"Lưu cài đặt",saving:"Đang lưu…",thanks:"Cảm ơn bạn đã hỗ trợ!",saved:"Đã lưu cài đặt",thanksDesc:"Lựa chọn của bạn đã được lưu. Vì đã bật ít nhất một tùy chọn, cửa sổ này sẽ không xuất hiện lại sau các bản cập nhật sau.",declinedDesc:"Không có tùy chọn nào được bật. Cửa sổ được ẩn cho phiên bản này và có thể được đề nghị lại sau một bản cập nhật sau.",done:"OK",error:"Không thể lưu cài đặt. Vui lòng thử lại."},
  ko:{title:"ANTHBOT Map 개발을 도와주시겠어요?",subtitle:"선택적으로 사용 통계와 진단 데이터를 공유하면 문제를 더 빠르게 해결하고 다양한 ANTHBOT 모델 지원을 개선하는 데 도움이 됩니다.",usageTitle:"사용 통계 공유",usageDesc:"통합 버전, Home Assistant 버전, 국가, 사용 중인 ANTHBOT 모델 수와 같은 최소한의 기술 데이터만 포함합니다. 사용자 이름, 비밀번호, 일련번호, GPS 위치 및 지도는 전송되지 않습니다.",diagTitle:"자동 진단 보고서 전송",diagDesc:"오류가 발생하면 개인정보 보호 필터를 거친 기술 진단 데이터를 개발 지원을 위해 전송할 수 있습니다. 이는 로봇을 변경하거나 제어하지 않습니다.",privacy:"데이터 공유는 완전히 선택 사항이며 언제든 끌 수 있습니다.",privacyLink:"개인정보 보호 안내",later:"나중에",save:"설정 저장",saving:"저장 중…",thanks:"도와주셔서 감사합니다!",saved:"설정 저장됨",thanksDesc:"선택이 저장되었습니다. 하나 이상의 옵션을 사용했으므로 향후 업데이트 후에는 이 창이 다시 나타나지 않습니다.",declinedDesc:"아무 옵션도 사용하지 않았습니다. 이 버전에서는 창이 숨겨지며 향후 업데이트 후 다시 제안될 수 있습니다.",done:"확인",error:"설정을 저장할 수 없습니다. 다시 시도하세요."},
  km:{title:"តើអ្នកចង់ជួយអភិវឌ្ឍ ANTHBOT Map ដែរឬទេ?",subtitle:"ដោយចែករំលែកស្ថិតិការប្រើប្រាស់ និងទិន្នន័យវិនិច្ឆ័យដោយស្ម័គ្រចិត្ត អ្នកអាចជួយឱ្យយើងកែបញ្ហាបានលឿន និងកែលម្អការគាំទ្រម៉ូដែល ANTHBOT ផ្សេងៗ។",usageTitle:"ចែករំលែកស្ថិតិការប្រើប្រាស់",usageDesc:"ទិន្នន័យបច្ចេកទេសអប្បបរមា ដូចជា កំណែ integration កំណែ Home Assistant ប្រទេស និងចំនួនម៉ូដែល ANTHBOT ដែលកំពុងប្រើ។ មិនផ្ញើឈ្មោះអ្នកប្រើ ពាក្យសម្ងាត់ លេខស៊េរី ទីតាំង GPS ឬផែនទីទេ។",diagTitle:"ផ្ញើរបាយការណ៍វិនិច្ឆ័យដោយស្វ័យប្រវត្តិ",diagDesc:"នៅពេលមានកំហុស អាចផ្ញើទិន្នន័យវិនិច្ឆ័យបច្ចេកទេសដែលបានត្រងសម្រាប់ឯកជនភាព ដើម្បីជួយការអភិវឌ្ឍ។ វាមិនកែប្រែ ឬបញ្ជារ៉ូបូតទេ។",privacy:"ការចែករំលែកទិន្នន័យគឺស្ម័គ្រចិត្តទាំងស្រុង ហើយអាចបិទបានគ្រប់ពេល។",privacyLink:"សេចក្តីជូនដំណឹងអំពីឯកជនភាព",later:"មិនមែនឥឡូវនេះ",save:"រក្សាទុកការកំណត់",saving:"កំពុងរក្សាទុក…",thanks:"សូមអរគុណសម្រាប់ការជួយ!",saved:"បានរក្សាទុកការកំណត់",thanksDesc:"ជម្រើសរបស់អ្នកត្រូវបានរក្សាទុក។ ដោយសារបានបើកយ៉ាងហោចណាស់មួយ ជំហាននេះនឹងមិនបង្ហាញម្ដងទៀតក្រោយការអាប់ដេតនាពេលអនាគត។",declinedDesc:"មិនបានបើកជម្រើសណាមួយទេ។ វានឹងលាក់សម្រាប់កំណែនេះ ហើយអាចសួរម្ដងទៀតក្រោយការអាប់ដេតនាពេលអនាគត។",done:"យល់ព្រម",error:"មិនអាចរក្សាទុកការកំណត់បានទេ។ សូមព្យាយាមម្តងទៀត។"},
};

const ANTHBOT_PRIVACY_URL = "https://github.com/Mqbretrofit/ha-anthbot-map-v2/blob/test/no-go-path-crossing-diagnostics/PRIVACY.md";
const ANTHBOT_OPTIN_HOST_ID = "anthbot-developer-optin-popup";

function anthbotOptinLanguage(hass) {
  const raw = String(hass?.locale?.language || hass?.language || "en").replaceAll("_", "-");
  if (ANTHBOT_OPTIN_SUPPORTED.has(raw)) return raw;
  const lower = raw.toLowerCase();
  if (lower.startsWith("zh")) {
    return /(?:-|_)(tw|hk|mo)(?:-|_|$)/i.test(raw) ? "zh-TW" : "zh-CN";
  }
  const base = raw.split("-")[0].toLowerCase();
  return ANTHBOT_OPTIN_SUPPORTED.has(base) ? base : "en";
}

function anthbotOptinHass() {
  const host = document.querySelector("home-assistant");
  return host?.hass || host?._hass || null;
}

async function anthbotOptinCall(hass, service, serviceData = {}) {
  const result = await hass.connection.sendMessagePromise({
    type: "call_service",
    domain: "anthbot_map",
    service,
    service_data: serviceData,
    return_response: true,
  });
  return result?.response || {};
}

function anthbotOptinShow(hass, state) {
  if (document.getElementById(ANTHBOT_OPTIN_HOST_ID)) return;
  const language = anthbotOptinLanguage(hass);
  const t = ANTHBOT_OPTIN_TEXT[language] || ANTHBOT_OPTIN_TEXT.en;
  const host = document.createElement("div");
  host.id = ANTHBOT_OPTIN_HOST_ID;
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host{position:fixed;inset:0;z-index:2147483646;font-family:var(--paper-font-body1_-_font-family,Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif)}
      *{box-sizing:border-box}.overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(0,0,0,.58);backdrop-filter:blur(2px)}
      .dialog{width:min(620px,100%);max-height:92vh;overflow:auto;border:1px solid var(--divider-color,#40505c);border-radius:20px;background:var(--card-background-color,#1c252d);color:var(--primary-text-color,#f3f6f8);box-shadow:0 28px 80px rgba(0,0,0,.55)}
      .head{display:flex;gap:14px;align-items:flex-start;padding:22px 24px 14px}.icon{display:grid;place-items:center;flex:0 0 48px;width:48px;height:48px;border-radius:15px;background:linear-gradient(135deg,var(--primary-color,#03a9d9),#607dff);color:#fff;font-size:24px}
      h1{margin:1px 0 7px;font-size:22px;line-height:1.25}.subtitle{font-size:14px;line-height:1.5;color:var(--secondary-text-color,#a9b6bf)}.body{padding:0 24px 6px}
      .choice{display:flex;align-items:flex-start;gap:12px;margin:11px 0;padding:15px 14px;border:1px solid var(--divider-color,#37454f);border-radius:14px;background:var(--secondary-background-color,#222d36);cursor:pointer}.choice:hover{border-color:var(--primary-color,#03a9d9)}
      .choice input{flex:0 0 auto;width:22px;height:22px;margin-top:3px;accent-color:var(--primary-color,#03a9d9)}.choice strong{display:block;margin-bottom:4px;font-size:15px}.choice span span{display:block;font-size:13px;line-height:1.45;color:var(--secondary-text-color,#a9b6bf)}
      .privacy{margin:14px 2px 4px;padding:13px 14px;border-radius:12px;background:color-mix(in srgb,var(--primary-color,#03a9d9) 8%,var(--card-background-color,#1c252d));font-size:12.5px;line-height:1.5;color:var(--secondary-text-color,#b8c8d2)}.privacy a{color:var(--primary-color,#62c7ed);font-weight:700;text-decoration:none}.error{display:none;margin:10px 2px 0;color:var(--error-color,#ff6b6b);font-size:13px}
      .actions{display:flex;justify-content:flex-end;gap:10px;margin-top:12px;padding:16px 24px 22px;border-top:1px solid var(--divider-color,#303d46)}button{min-height:42px;padding:9px 16px;border:1px solid var(--divider-color,#4a5964);border-radius:11px;background:var(--secondary-background-color,#26333c);color:var(--primary-text-color,#fff);font:inherit;font-weight:700;cursor:pointer}button.primary{border:0;background:var(--primary-color,#03a9d9);color:var(--text-primary-color,#fff);padding-inline:20px}button:disabled{opacity:.55;cursor:wait}
      .thanks{padding:34px;text-align:center}.thanks .big{margin-bottom:10px;font-size:42px}.thanks h2{margin:0 0 9px}.thanks p{line-height:1.5;color:var(--secondary-text-color,#a9b6bf)}
      @media(max-width:600px){.overlay{padding:10px}.dialog{border-radius:16px}.head{padding:18px 17px 12px}.body{padding:0 17px 5px}.actions{flex-direction:column-reverse;padding:14px 17px 18px}button{width:100%}}
    </style>
    <div class="overlay"><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="anthbot-optin-title">
      <div class="head"><div class="icon">♥</div><div><h1 id="anthbot-optin-title"></h1><div class="subtitle"></div></div></div>
      <div class="body">
        <label class="choice"><input id="usage" type="checkbox"><span><strong id="usage-title"></strong><span id="usage-desc"></span></span></label>
        <label class="choice"><input id="diagnostics" type="checkbox"><span><strong id="diag-title"></strong><span id="diag-desc"></span></span></label>
        <div class="privacy"><span id="privacy-text"></span> <a id="privacy-link" target="_blank" rel="noopener noreferrer"></a></div>
        <div class="error" id="error"></div>
      </div>
      <div class="actions"><button id="later" type="button"></button><button id="save" class="primary" type="button"></button></div>
    </section></div>`;

  root.getElementById("anthbot-optin-title").textContent = t.title;
  root.querySelector(".subtitle").textContent = t.subtitle;
  root.getElementById("usage-title").textContent = t.usageTitle;
  root.getElementById("usage-desc").textContent = t.usageDesc;
  root.getElementById("diag-title").textContent = t.diagTitle;
  root.getElementById("diag-desc").textContent = t.diagDesc;
  root.getElementById("privacy-text").textContent = t.privacy;
  const privacyLink = root.getElementById("privacy-link");
  privacyLink.textContent = t.privacyLink;
  privacyLink.href = ANTHBOT_PRIVACY_URL;
  const usage = root.getElementById("usage");
  const diagnostics = root.getElementById("diagnostics");
  usage.checked = state?.share_anonymous_usage === true;
  diagnostics.checked = state?.send_automatic_diagnostics === true;
  root.getElementById("later").textContent = t.later;
  root.getElementById("save").textContent = t.save;
  root.getElementById("error").textContent = t.error;

  const setBusy = (busy) => {
    root.getElementById("later").disabled = busy;
    root.getElementById("save").disabled = busy;
    root.getElementById("save").textContent = busy ? t.saving : t.save;
  };
  const showError = () => { root.getElementById("error").style.display = "block"; };
  const close = () => host.remove();
  const showThanks = (accepted) => {
    const dialog = root.querySelector(".dialog");
    dialog.innerHTML = `<div class="thanks"><div class="big">✓</div><h2></h2><p></p><button class="primary" id="done" type="button"></button></div>`;
    dialog.querySelector("h2").textContent = accepted ? t.thanks : t.saved;
    dialog.querySelector("p").textContent = accepted ? t.thanksDesc : t.declinedDesc;
    dialog.querySelector("#done").textContent = t.done;
    dialog.querySelector("#done").addEventListener("click", close);
  };

  root.getElementById("later").addEventListener("click", async () => {
    setBusy(true);
    try {
      await anthbotOptinCall(hass, "developer_reporting_update", { dismissed: true });
      close();
    } catch (error) {
      console.warn("ANTHBOT developer opt-in dismissal failed", error);
      setBusy(false);
      showError();
    }
  });
  root.getElementById("save").addEventListener("click", async () => {
    setBusy(true);
    try {
      const accepted = usage.checked || diagnostics.checked;
      await anthbotOptinCall(hass, "developer_reporting_update", {
        share_anonymous_usage: usage.checked,
        send_automatic_diagnostics: diagnostics.checked,
      });
      showThanks(accepted);
    } catch (error) {
      console.warn("ANTHBOT developer opt-in save failed", error);
      setBusy(false);
      showError();
    }
  });

  document.body.appendChild(host);
}

async function anthbotInstallDeveloperOptinPopup() {
  if (window.__anthbotDeveloperOptinInstalled) return;
  window.__anthbotDeveloperOptinInstalled = true;

  // The resource can load before the integration platforms/services finish
  // setting up. Retry quietly; never block Home Assistant or mower controls.
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const hass = anthbotOptinHass();
    if (!hass?.connection) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      continue;
    }
    // Reporting preferences are installation-global; only an administrator
    // may make that choice for the Home Assistant installation.
    if (hass.user && hass.user.is_admin === false) return;
    try {
      const state = await anthbotOptinCall(hass, "developer_reporting_get");
      if (state?.installed && state?.should_show) anthbotOptinShow(hass, state);
      return;
    } catch (_error) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
  }
}

void anthbotInstallDeveloperOptinPopup();
