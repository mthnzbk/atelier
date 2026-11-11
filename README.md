# Atelier · Python Studio

Sürüm 9.4.0.

Bir proje ilk açıldığında **Güven ver** veya **Kısıtlı aç** seçeneklerinden birini seçin. Kısıtlı projede dosya düzenleme, renklendirme ve arama kullanılabilir. Proje Python'u, LSP, çalıştırma, debugger, testler, Git ve terminal güven verildiğinde etkinleşir. Karar proje klasörüne göre kaydedilir ve durum çubuğundaki **Proje güveni** düğmesinden değiştirilebilir.

Durum çubuğundaki **Python** düğmesi veya **Çalıştır → Python durumu…** seçili yorumlayıcıyı, sürümünü, seçim nedenini ve dil sunucusunun durumunu gösterir. Taşınmış bir sanal ortamın temel Python'u bulunamazsa Atelier sonraki geçerli yorumlayıcıya geçer ve nedeni panelde gösterir. Aynı panelden Python seçebilir, ortamları yeniden tarayabilir ve LSP'yi yeniden başlatabilirsiniz.

**Python durumu → Proje ortamını hazırla…** proje kökünde `.venv` oluşturur veya mevcut ortamı kullanır. `requirements.txt` ve `pyproject.toml` birlikte varsa bağımlılık kaynağını seçebilirsiniz. Kurulum onaydan sonra başlar. Başarılı olduğunda Atelier ortamı projeye kaydeder ve LSP’yi yeniden başlatır.

**Çalıştır → Çalıştırma profilleri… → Yeni** ile giriş dosyasını ve çalışma dizinini dosya seçiciden belirleyin. Argümanları girip **Tamam** ile kaydedin. Araç çubuğunda Çalıştır ve Debug düğmelerinin yanındaki listeden profili değiştirebilirsiniz. Profilin üzerine gelince giriş dosyası ve Python yolu görünür. Çalıştır ve Debug aynı profili kullanır.

**Dosya → Son projeler…** (`Ctrl+Alt+P`) daha önce açtığınız projeleri listeler. Sık kullandığınız projeleri **Sabitle** ile listenin başına alın. Komut paletinde proje adını arayarak klasörüne ve kayıtlı oturumuna dönebilirsiniz.

`Ctrl+Tab` son kullanılan sekmeye geçer. Ctrl'yi basılı tutup Tab'a tekrar basarak diğer sekmelere geçebilir, Shift ile yönü tersine çevirebilirsiniz. `Ctrl+Shift+T` kapatılan dosya sekmesini diskteki içeriğiyle ve önceki imleç konumuyla açar.

JSON, YAML, HTML, CSS, JavaScript ve TOML dosyaları otomatik renklendirilir. HTML'de `<di` yazıp öneriyi seçerek etiket ekleyin veya Ctrl+Space ile önerileri açın. `html5`, `a`, `img`, `link`, `form`, `input`, `table` ve `script` kısaltmaları Tab ile genişler. Tab sonraki düzenlenebilir alana geçer.

HTML, CSS, JavaScript, JSON, YAML ve TOML dosyalarında bir girinti düzeyi iki boşluktur. JSON, YAML ve TOML hataları yazarken editörde ve **Sorunlar** panelinde görünür. YAML doğrulaması için uygulamayı çalıştırdığınız Python ortamına `requirements.txt` bağımlılıklarını kurun.

**Kod → Kodu biçimlendir** (`Shift+Alt+F`) HTML, CSS, JavaScript ve JSON üzerinde çalışır. Kayıt sırasında çalıştırmak için **Ayarlar → Python → Kaydederken HTML, CSS, JavaScript ve JSON biçimlendir** seçeneğini açın veya `atelier.toml` dosyasındaki `[save]` bölümüne `format_web_on_save = true` ekleyin.

JSON biçimlendirmesi yerleşiktir. HTML girintilerini DjHTML düzenler. CSS ve JavaScript için CSS Beautifier ve JS Beautifier kullanılır. Üç araç da `requirements.txt` üzerinden uygulamanın Python ortamına kurulur.

`.sql` dosyaları otomatik renklendirilir. `examples/order_summary.sql`, SQLite üzerinde örnek müşteri ve sipariş verileriyle çalışan bir sorgu içerir.

**Dosya → Paylaşılabilir proje ayarları…** proje kökünde `atelier.toml` dosyasını açar. Aşağıdaki örnek bir çalıştırma profili, bir test görevi ve kayıt ayarları tanımlar.

```toml
default_profile = "app"

[save]
format_on_save = true
sort_imports = true

[tasks.test]
label = "Testleri çalıştır"
args = ["-m", "pytest", "tests", "-q"]
cwd = "."

[profiles.app]
file = "app.py"
args = ["--port", "8000"]
```

**Çalıştır → Proje komutları…** ve komut paleti görevleri seçili Python ortamında çalıştırır. Görev ve profillerde `args` bir dizi, `cwd` proje içi göreli dizin ve isteğe bağlı `env` metin değerlerinden oluşan bir tablodur. Paylaşılan `[save]` değerleri ve aynı adlı profiller yerel tanımlardan önceliklidir. Etkin profil seçimi, Python yolu ve pencere düzeni makineye özel kalır.

**Çalıştır → Proje komutları…** penceresinde komut ekleyebilir, düzenleyebilir veya silebilirsiniz. Formda komut adını, Python argümanlarını ve çalışma klasörünü girin. Boşluk içeren argümanları tırnak içine alın. **Kaydet** değişikliği `atelier.toml` dosyasına yazar ve komut paletinde görünür hâle getirir.

## Günlük çalışma araçları (v9)

- **Git çakışmaları:** Git panelinde **Çakışmaları çöz…** veya çakışmalı dosyanın sağ tık menüsü. Yerel ve gelen parçayı yan yana görün; her parçada bir tarafı veya ikisini seçin. Düzenlenebilir sonucu editöre aktarabilir ya da kaydedip Git için hazırlayabilirsiniz. Normal ve `diff3` işaretleri desteklenir. İşaretsiz silme/ikili dosya çakışmaları için Git kullanın. Rebase sırasında ilk ve ikinci taraf, Git'in dosyaya yazdığı sırayı izler.
- **Kayıt işlemleri:** Ayarlar → Python sayfasında proje bazında biçimlendirme, import düzenleme, satır sonu boşluklarını temizleme ve son satıra satır sonu ekleme. Dosya hemen kaydedilir; işlemler arka planda tamamlanır ve belge veya disk içeriği değişmişse eski sonuç atlanır. Aynı anda iki işlem yürür, diğerleri sıraya girer. Otomatik import düzenleme kullanılmayan importları silmez. Boşluk temizleme Python çok satırlı dizgilerini ve Markdown satır sonu işaretlerini korur.
- **Proje sembolleri:** `Ctrl+T` ile sınıf, fonksiyon ve metot adı arayın. Açık Python dosyalarının kaydedilmemiş içeriği de taranır. Sonuca çift tıklayarak veya Enter ile tanıma gidin. Tarama iptal edilebilir; en çok 3.000 Python dosyası ve 10.000 sembol işlenir.
- **Debugger:** Seçili çağrı çerçevesinin satırı editörde vurgulanır. Duraklatıldığında bir değişken adının üzerine gelerek türünü ve değerini görün. **Kesme noktalarını yönet…** ile açık dosyalardaki noktaları listeleyin, konumlarına gidin, koşullarını düzenleyin veya kaldırın.
- **Büyük dosyalar:** 1 milyon karakter, 20.000 satır veya 20.000 karakterlik satır eşiği aşıldığında durum çubuğunda **Büyük dosya modu** görünür. Düzenleme ve kaydetme devam eder; o belge için LSP, yoğun renklendirme, katlama, minimap, Markdown önizleme ve otomatik kayıt işlemleri devre dışı kalır. Diskten açma sınırı 25 MB.
- **Arama ve kararlılık:** Proje araması ve değiştirme önizlemesi durdurulabilir ayrı süreçlerde çalışır. Eski bir aramanın sonucu yeni projeye veya aramaya taşınmaz. Git durum yenilemeleri hızlı sekme geçişlerinde birleştirilir; gereksiz Git okuma süreçleri durdurulur.

Günlük çalışma kontrollerini `python -m unittest -v tests.test_daily_workflows` ile çalıştırabilirsiniz. Testler gerçek Windows terminali, debugger ve geçici Git deposu kullanır.

## Python ortamları ve paketler (v8)

**Kod → Python ortamları ve paketler…** veya **Ayarlar → Python → Yönet** ile açın.

- Projenin `.venv`/`venv` ortamları, hatırlanan Python yolları, PATH'teki Python, Windows kayıtlı Python kurulumları ve yaygın kullanıcı ortam klasörleri keşfedilir. Gözat ile başka bir Python ekleyebilirsiniz. Sürüm, ortam türü ve pip durumu seçildiğinde doğrulanır.
- Üstte temel Python'u seçip **Ortam oluştur** sekmesinden yeni bir sanal ortam oluşturun. Mevcut klasörlerin üzerine yazılmaz. İşlem bitince **Bu proje için kullan** ile etkinleştirin; tercih QSettings'te proje bazında saklanır. Daha önce ortam seçilmemiş projelerde mevcut `.venv`/`venv` otomatik bulunur.
- **Paketler** sekmesinde kurulu paketleri filtreleyin, paket adı ve isteğe bağlı sabit sürümle kurun, güncellemeleri denetleyin, seçili paketleri güncelleyin veya onayla kaldırın. Tüm pip işlemleri üstte seçili Python ile çalışır; seçim proje ortamından farklı olabilir.
- `requirements.txt` dosyasından kurma, kurulu paketleri `pip freeze` ile dosyaya aktarma ve `pip check` ile bağımlılık tutarlılığı denetleme desteklenir. Dışa aktarma bir kilit dosyası oluşturmaz; mevcut kurulu ortamı kaydeder. Eksik pip için **pip kur / onar**, pytest/coverage/debugpy için **Test / debug araçlarını kur** bulunur.
- İşlemler arka planda yürür; çıktı ve hatalar aynı ekranda gösterilir. Durdurulan bir paket işlemi kısmen uygulanmış olabilir; listeyi yenileyip bağımlılık kontrolünü çalıştırabilirsiniz. Başarısız ortam oluşturma sonrası kalan klasörü otomatik silmeyiz; yeniden denemek için yeni bir klasör seçin.
- Ortam değişince LSP yeniden bağlanır; sonraki çalıştırma ve testler seçilen ortamı kullanır. LSP sunucusu editörün kendi ortamında, Jedi analizi proje Python'unda çalışır. Çalıştırma profilinde açıkça belirtilen Python önceliklidir. Açık program ve terminal süreçleri değiştirilmez; terminalin yeni ortamı alması için **Yeni terminal** seçin.
- Proje Python'unda PySide6/LSP kurulması gerekmez. Projenizin bağımlılıklarını ve kullanacağınız test araçlarını o ortama ayrıca kurun. Conda/Poetry ortamı oluşturma veya çözümleyici yönetimi bu sürümde yoktur; mevcut Python çalıştırılabilir dosyaları seçilebilir.

Ortam kontrollerini `python -m unittest -v tests.test_environment_management` ile çalıştırabilirsiniz. Testler geçici bir sanal ortam ve yerel paket kullanır.

## v7 yenilikleri

- **Parametre bilgisi:** aktif parametre vurgulanır; ‹/› ile farklı imzalar seçilir. Ctrl+Shift+Space yeniden gösterir.
- **Import yönetimi:** Kod → Eksik import ekle; standart kütüphane ve proje sembolleri için öneri/önizleme. Ctrl+Alt+O kullanılmayan/tekrarlanan importları kaldırıp sıralar. Dinamik importlar otomatik çözümlenmez; önizlemeyi kontrol edin.
- **Refactor:** seçili ifadeyi değişkene veya kod bloğunu fonksiyona çıkarma; değişiklikler önce gösterilir. İşlemden önce dosya kaydedilir.
- **Dosya geçmişi:** her kayıt öncesi/sonrası içerik kullanıcı veri klasöründe sıkıştırılarak saklanır (dosya başına son 40 farklı sürüm). Dosya → Dosya geçmişi ile farkı görün ve seçilen sürümü editöre yükleyin; diske yazmak için ayrıca kaydedin.
- **Çalıştırma profilleri:** Çalıştır menüsünden dosya, Python, çalışma dizini, argümanlar ve KEY=value ortam değişkenleriyle proje bazlı profiller oluşturun. Seçili profil normal çalıştırma ve debugger için kullanılır.
- **Tıklanabilir hata çıktısı:** Python traceback satırındaki dosya/satır bilgisine tıklayın; ilgili konum açılır.
- **Dosya ağacı:** Ctrl/Shift ile çoklu seçim; menüde toplu açma, tek Git add komutuyla hazırlama, önizlemeli toplu yeniden adlandırma, tek tek Python refactor'u, yolları kopyalama ve toplu geri dönüşüm kutusu.
- **Ayarlar/tema:** kısayol alanları ve satırları büyütüldü. Eksik denetimler, açılır listeler, yerel palet, imza penceresi, kaydırma ve devre dışı durumlar temaya bağlandı.
- **Terminal:** arka plan program çıktısı artık terminalden çıktı sekmesine zorla geçmez. Değişmeyen metin yeniden çizilmez; aynı terminal boyutu tekrar gönderilmez. Kaydırma çubuğu/boyut geri beslemesi ve başlangıçtaki geçici süreç durumu düzeltildi.

Python araçlarını `python -m unittest -v tests.test_python_tools` ile sınayabilirsiniz. Windows terminali gerçek konsol bağlantısı gerektirir.

v6 için derleme ve paketleme yapılmadı. Mevcut sanal ortamda `python -m pip install -r requirements.txt` ve ardından `python main.py` kullanın. Aşağıdaki hazır Windows paketine ilişkin bölüm önceki sürümler içindir.

## v6 kullanım özeti

- **Ctrl+P:** dosya adının birkaç harfiyle hızlı açma; `.git`, sanal ortam ve derleme klasörleri taranmaz.
- **Ctrl+D:** önce kelimeyi seçer, tekrar basıldığında sonraki eşleşmeye imleç ekler. Alt+tıklama da ek imleç oluşturur. Yazma, silme, yapıştırma ve satır ekleme bütün imleçlere uygulanır; Esc çoklu imleci bitirir.
- **Ctrl+. :** LSP'nin bu konum için sunduğu hızlı düzeltmeleri listeler.
- **Bul/değiştir:** Aa, `.*` regex ve tam kelime seçenekleri. Regex değiştirmede `\1` gibi gruplar kullanılabilir. Proje aramasında `*.py, *.md` gibi dosya filtreleri vardır.
- **Yan yana Git:** Görünüm → Yan yana Git karşılaştırması. Index/çalışma dosyası veya HEAD/index karşılaştırılır; bir değişiklik grubunu seçip hazırlayın ya da hazırlamadan çıkarın. Yeni dosyalar bütün olarak hazırlanır/çıkarılır. Çalışma dosyası korunur.
- **Test kapsamı:** Ayarlar → Testler → Kapsamı ölç. Test çalıştırıldığında ölçülen satırlar yeşil, çalışmayan satırlar kırmızı işaretlenir; kapsam tablosundan eksik satıra gidilebilir. Seçilen Python ortamında coverage kurulu olmalıdır.
- **Ayarlar:** Editör, Görünüm, Python, Git, Testler ve Kısayollar sekmeleri. Tercihler QSettings'e kaydedilir. Python yolu, çalıştırma ve pytest argümanları mevcut projeye aittir.
- **Katlama:** numara alanındaki paralel çizgiler kaldırıldı; açık/kapalı durum için sade oklar kullanılır. Kod içinde yalnızca imlecin bulunduğu en içteki bloğun ince kılavuzu gösterilir. Görünüm ayarından bu kılavuz da kapatılabilir.
- **Logo** `atelier/assets/atelier-logo.png` pencere, uygulama ve kenar paneli için kullanılır. Görsel üretim bilgisi `docs/logo-generation.md` içindedir.

Editör kontrollerini `python -m unittest -v tests.test_editing_features` ile çalıştırabilirsiniz.

PySide6 tabanlı, yerel çalışan Python editörü. Python 3.10 veya üzeri gerekir.

## Kurulum

**Hazır Windows x64 paketi:** Python dahil Windows ZIP dosyasının tamamını çıkarın. `kur.cmd` kullanıcı hesabınıza kurar ve masaüstü/Başlat menüsü kısayollarını oluşturur; yönetici izni ve internet gerekmez. Kurmadan denemek için `Atelier.cmd` kullanın. Git ayrıca kurulu olmalıdır. Kaldırma için kurulum klasöründeki `uninstall.ps1` kullanılabilir. Kendi projelerinizi kurulum klasörünün dışında tutun. Bu paket Python 3.14.10 içerir; aşağıdaki adımlar yalnızca kaynak kod paketini elle çalıştırmak içindir.

ZIP içindeki bütün dosyaları aynı klasöre çıkarın. Önceki sürümü güncelliyorsanız yalnızca main.py dosyasını değil bütün paketi kopyalayın.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade -r requirements.txt
.venv/bin/python main.py
```

Windows Python kısayolu çalışmıyorsa python.org üzerinden gerçek bir Python kurulumu gerekir.

Kurulumdan sonra Windows'ta baslat.bat dosyasına çift tıklayarak editörü açabilirsiniz.

## Neler var?

- Klasör tabanlı proje ağacı, taşınabilir ve kapatılabilir dosya sekmeleri.
- Aynı belgeyi paylaşan iki editör görünümü; değişiklikler iki tarafta birlikte görünür.
- Python renklendirme, satır numaraları, etkin satır vurgusu.
- Yazarken tamamlama ve Ctrl+Space; Enter/Tab ile öneri ekleme, Esc ile kapatma.
- Fonksiyon/metot/sınıf tamamlaması `()` ekler ve imleci içine yerleştirir. Mevcut parantez çoğaltılmaz; import satırında çağrı parantezi eklenmez.
- LSP hata ve uyarıları: kırmızı/sarı zigzag çizgiler, kenar işaretleri, dosyalar arasında ortak sorun listesi.
- Fareyle üzerine gelince açıklama ve tanı mesajı; parantez açarken/virgül yazarken parametre ipucu.
- F12 ile tanıma gitme, F2 ile LSP üzerinden sembol yeniden adlandırma. Çoklu dosya değişiklikleri sekmelerde açılır; Ctrl+Alt+S ile kaydedilir.
- Dosyada bul/değiştir ve proje genelinde arama/değiştirme. Projedeki değişiklikler uygulanmadan dosya listesi ve eşleşme sayısı gösterilir.
- Eşleşen parantez/tırnak ekleme, parantez üzerinden geçme, çift silme, otomatik girinti, Tab/Shift+Tab ile girinti ve satır yorumlama.
- autopep8 üzerinden biçimlendirme ve isteğe bağlı kaydederken biçimlendirme.
- Python yorumlayıcısı/sanal ortam seçimi: tamamlama seçilen ortamı kullanır; programlar aynı yorumlayıcıyla çalıştırılır.
- Çalıştırma, çıktı paneli, program argümanları, standart girdiye metin gönderme ve durdurma.
- debugpy ile kesme noktaları, devam, duraklat, adımla ilerle, içine gir/dışına çık; çağrı yığını ve genişletilebilir değişken ağacı.
- Kalıcı gömülü terminal: Windows ConPTY, Unix PTY; komut geçmişi, etkileşimli Python, Ctrl+C ve pano desteği.
- Kod katlama, Markdown başlık/bölüm katlama ve tıklanabilir minimap.
- Markdown renklendirme; kaynak, canlı belge önizlemesi ve üretilmiş HTML kaynağı; HTML dışa aktarma.
- Dosya dışarıda değiştiğinde/silindiğinde bildirim; karşılaştırma, yeniden yükleme ve yerel içeriği koruma seçenekleri. Dış değişikliklerin üzerine kaydetmek onay ister.
- Git değişiklik listesi, HEAD ile fark ve kenar işaretleri; dosya hazırlama/hazırlamadan çıkarma, commit, geçmiş, dal oluşturma/değiştirme ve upstream için push/pull.
- Gece/açık tema, yazı tipi ve boyut ayarları; son proje ve ortam tercihlerinin saklanması.
- Kaydedilmemiş dosya uyarıları ve mevcut dosyayı kesintili yazmalardan koruyan atomik kayıt.
- Snippet şablonları: `def`, `class`, `for`, `if`, `while`, `try`, `with`, `main`, `test`; Tab/Shift+Tab ile alanlar arasında gezinme.
- Ctrl+Shift+P ile aranabilir komut paleti; ok tuşları ve Enter ile seçim.
- pytest test paneli: keşif, tümünü/seçileni çalıştırma, sonuç ve hata ayrıntıları, çift tıklayarak hatalı satıra gitme.
- Koşullu kesme noktaları, izlenen ifadeler ve debugger duraklamışken değişken değerini değiştirme.
- Kaydedilmemiş içerik için iki saniyede bir kurtarma kaydı; açık sekmeler, imleçler, katlanan bloklar, bölünmüş görünümler, kesme noktaları ve izlenen ifadeleri geri yükleme.
- QSettings ile pencere boyutu/konumu ve maximized durumu, araç çubuğu/panel düzeni, panel boyutları ve seçili sekmeleri, tema, yazı tipi, Python ortamı ve editör tercihlerini saklama.
- Git panelinde Depo başlat düğmesi; proje ağacında izlenmeyen/hazırlanmamış/hazırlanmış dosyaları farklı renklerle gösterme.
- Artımlı satır renklendirme, önbellekli/örneklemeli minimap ve değişmeyen dosyaları tekrar hash'lemeyen izleme.
- Her proje için ayrı Python ortamı, çalıştırma argümanları ve pytest seçenekleri.
- Sembol kullanımları, filtrelenebilir fonksiyon/sınıf listesi ve geri/ileri kod konumu geçmişi.
- Seçili kod satırlarını önizleyerek yalnızca Git index'ine hazırlama; diğer değişiklikleri çalışma dosyasında bırakma.
- Dosya ağacı sağ tık menüsü: dosya/klasör oluşturma, yeniden adlandırma, Python modül/paket refactor'u, geri dönüşüm kutusuna gönderme ve Git add.
- Çevrimdışı Material Design Icons simgeleri (QtAwesome/mdi6); satır alanında ve kod girintilerinde blok boyunca dikey kılavuzlar.
- Windows hazır paketinde kullanıcı tarafından seçilen ZIP üzerinden güncelleme; bütünlük kontrolü, eski uygulama yedeği ve kopyalama hatasında geri dönüş.

## Kısayollar

| İşlem | Kısayol |
|---|---|
| Yeni / aç / kaydet | Ctrl+N / Ctrl+O / Ctrl+S |
| Proje klasörü aç | Ctrl+Shift+O |
| Farklı kaydet / tümünü kaydet | Ctrl+Shift+S / Ctrl+Alt+S |
| Sekmeyi kapat | Ctrl+W |
| Bul / değiştir / projede ara | Ctrl+F / Ctrl+H / Ctrl+Shift+F |
| Tamamlama | Ctrl+Space |
| Tanıma git / yeniden adlandır | F12 / F2 |
| Biçimlendir | Shift+Alt+F |
| Satır yorumunu aç/kapat | Ctrl+/ |
| Editörü böl/birleştir | Ctrl+Backslash |
| Kenar / alt panel | Ctrl+B / Ctrl+J |
| Çalıştır / durdur | F5 / Shift+F5 |
| Debug başlat / devam et | Ctrl+F5 / F6 |
| Kesme noktası | F9 veya satır numarası alanına tıklama |
| Satırı geç / içine gir / dışına çık | F10 / F11 / Shift+F11 |
| Terminali aç | Görünüm → Terminali aç veya Ctrl+` |
| Bloğu katla/aç | Ctrl+Shift+[ veya satır numarasının sağındaki −/+ |
| Tüm blokları aç | Ctrl+Shift+] |
| Komut paleti | Ctrl+Shift+P |
| Son kullanılan sekmeye geç | Ctrl+Tab |
| Son kullanılan sekmelerde geri git | Ctrl+Shift+Tab |
| Kapatılan dosya sekmesini aç | Ctrl+Shift+T |
| Test paneli | Ctrl+Alt+T |
| Koşullu kesme noktası | Shift+F9 |
| Kullanıldığı yerleri bul | Shift+F12 |
| Dosyanın fonksiyon/sınıf listesi | Ctrl+Shift+M |
| Önceki / sonraki kod konumu | Alt+Sol / Alt+Sağ |

## İlk deneme

1. Proje menüsünden kendi klasörünüzü açın.
2. Python ortamı düğmesinden projenizin .venv/Scripts/python.exe dosyasını seçin (Unix: .venv/bin/python).
3. Altta LSP hazır yazısını bekleyin. Editörün kurulduğu ortamda requirements.txt paketleri bulunmalıdır. Projenin bağımlılıkları ise seçtiğiniz proje ortamında olmalıdır.
4. examples/demo.py dosyasını açıp F5 ile çalıştırın.
5. 16. satıra kesme noktası koyup Ctrl+F5 ile başlatın. Debugger panelinde değişkenleri inceleyin; F10 ile ilerleyin.

## Yeni araçların kullanımı

**Markdown:** examples/guide.md dosyasını açın. Belgenin üstündeki seçimden Kaynak, Kaynak + Önizleme, Önizleme veya HTML kaynağı görünümünü seçin. Önizleme kısa bir gecikmeyle otomatik güncellenir. Yerel görseller belge klasörüne göre çözülür; HTML dışa aktar düğmesi üretilen sayfayı kaydeder. Önizleme Qt rich text motorunu kullanır; bir web tarayıcısının bütün CSS/JavaScript özelliklerini içermez.

**Dış dosya değişikliği:** Üst bildirim çubuğundan Yeniden yükle, Karşılaştır veya Yerel içeriği tut seçilir. Yerel içerik korunursa sonraki kayıt sırasında disk sürümünün üzerine yazılması ayrıca sorulur. Diskten yeniden yükleme, kaydedilmemiş yerel değişiklik varsa onay ister. Editörün kendi kaydı dış değişiklik uyarısı üretmez.

**Terminal:** Güvenilir proje açıldığında ilk terminal hazır olur. Terminal panelindeki **+** ile bağımsız oturumlar ekleyebilirsiniz. Projeler arasında geçişte her projenin oturumları ve çıktısı korunur. Shell proje klasöründe başlar ve seçili Python ortamı PATH üzerinde öne alınır. **Yeniden başlat** etkin oturumu güncel ortamla yeniden açar. Python REPL ve input() desteklenir. Ctrl+C çalışan komutu keser (metin seçiliyse kopyalar), Ctrl+V yapıştırır. Her terminal 3000 satırlık geçmiş tutar, VT kontrol dizilerini işler ve çıktıyı tek renk gösterir.

Windows'ta proje ortamı etkinleştirildiğinde komut isteminde bekleyen terminal yeni ortamla yeniden açılır. Çalışan komutlar ve yazılmakta olan komut satırı mevcut oturumda kalır. Bu davranışı **Ayarlar → Python** sekmesinden değiştirebilirsiniz.

**Katlama/minimap:** Satır numarasının sağındaki −/+ işareti bloğu katlar/açar; numaranın sol kısmı debugger kesme noktası içindir. Katlama iki bölünmüş görünüm arasında ortaktır. Sağdaki minimap'e tıklayarak veya sürükleyerek dosyada gezinin. Görünüm menüsünden minimap kapatılabilir. Python katlama, kod eksikken de çalışabilmesi için girintiye göre hesaplanır.

**Git:** Git panelinden dosyayı seçip Hazırla (+) kullanın; kaydedilmemiş dosya önce kaydedilir. Hazırlamayı kaldır yalnızca index'i değiştirir, çalışma dosyasını silmez. Commit penceresi hazırlanmış dosyaları ve mesajı gösterir. Dallar penceresinden yeni dal oluşturulabilir veya seçili dala geçilebilir; geçiş öncesinde yerel belgeleri kaydedin. Push/pull açık onay ister, upstream gerektirir ve pull yalnızca fast-forward kabul eder. Kimlik doğrulaması gerekiyorsa terminalden giriş yapın. Depo başlatmak için terminalde `git init` kullanın.

Git panelindeki **Depo başlat (git init)** düğmesi aynı işlemi proje klasörünü göstererek yapar. Dosya ağacında gri ad izlenmeyen dosyayı, sarı ad hazırlanmamış değişikliği, yeşil ad hazırlanmış ve commit bekleyen dosyayı, kırmızı çakışmayı gösterir. Hem hazırlanmış hem yeni kaydedilmiş değişikliği olan dosya sarıdır; ayrıntısı fareyle üzerinde bekleyince görünür. Bu renkler diskteki Git durumunu gösterir; henüz kaydedilmemiş içerik sekmedeki ● işaretiyle belirtilir.

**Snippet:** `def` yazıp Tab'a basın; fonksiyon adı seçilir. Adını yazıp Tab ile parametreye, tekrar Tab ile gövdeye geçin. Shift+Tab önceki alana döner, Esc şablon gezinmesini bitirir. Şablonlar tamamlama listesinde de “şablon” olarak gösterilir.

**Oturum ve kurtarma:** Görünüm → Tema ve yazı tipi penceresinden önceki oturumu geri yükleme ve otomatik kurtarma açılıp kapatılabilir. Kurtarma dosyası, kendi proje dosyalarınıza yazmadan kullanıcıya özel uygulama veri klasöründe tutulur. Beklenmedik kapanmadan sonra kaydedilmemiş içerik geri gelir; dosyası olan kurtarılan içerik kaydedilmeden önce disk sürümüyle karşılaştırılabilir. Normal kapatmada Kaydet/Vazgeç/İptal seçiminiz geçerlidir; Vazgeç dediğiniz değişiklik yeniden getirilmez. Dosya → Oturumu şimdi yedekle manuel kayıt alır. Pencere ve panel düzeni QSettings üzerinden sonraki açılışta uygulanır.

**Testler:** Ctrl+Alt+T → Keşfet. Proje ortamında pytest bulunmalıdır (hazır pakette vardır). Tümünü çalıştır veya Seçileni çalıştır kullanın. Başarısız testin ayrıntısını seçerek okuyun; çift tıklayarak hatalı satıra gidin. Test paneli çalıştırmadan önce değiştirilmiş belgeleri kaydeder.

**Gelişmiş debugger:** Bir satırda Shift+F9 ile koşul yazın (ör. `i == 2`). Debugger yalnızca koşul doğru olduğunda durur. Alt paneldeki ifade alanına `len(items)` gibi bir ifade yazıp İzle düğmesini kullanın. Program durduğunda değer hesaplanır. Değişken ağacındaki bir değişkene çift tıklayıp yeni Python değerini girerek değiştirebilirsiniz. İzlenen ifadeler gerçek Python ifadeleridir; fonksiyon çağrıları programın durumunu değiştirebilir.

## v5 araçları

**Proje ayarları:** Dosya → Proje ayarları. Python yolu, çalıştırma argümanları ve `-k smoke --maxfail=1` gibi pytest seçenekleri proje klasörüne göre QSettings içinde ayrı tutulur. Proje değiştirince ilgili tercihler yüklenir; terminali yeni ortamla açmak için Yeni terminal kullanın.

**Kod gezinmesi:** Shift+F12 sembolün kullanımlarını alt panelde listeler. Ctrl+Shift+M açık dosyanın sembollerini listeler; üst kutuyla filtreleyin ve bir sonuca tıklayın. F12 ile yapılan dosyalar arası atlamadan sonra Alt+Sol/Alt+Sağ konum geçmişinde gezinir.

**Dosya ağacı:** Dosya/klasöre sağ tıklayın. Silme geri dönüşüm kutusuna gider; kalıcı silme yedeği yoksa uygulanmaz. Açık ve değiştirilmiş dosyalar için önce kaydetme seçimi sunulur. Normal yeniden adlandırma yalnızca dosya/klasör adını değiştirir. Refactor seçeneği Python modül/paket adıyla birlikte Rope'un bulduğu import referanslarını günceller; önizlemeyi onaylamadan değişiklik yapılmaz. Dinamik importlar ve Python dışındaki metin referansları otomatik olarak bulunamayabilir. Proje kökü ve .git klasörü bu menüden silinemez; sembolik bağlantılar için refactor uygulanmaz.

**Git satır seçimi:** İzlenen bir dosyada istediğiniz satırları seçin; Kod → Seçili satırları Git için hazırla. Değişiklikler index'in mevcut içeriğine karşı hesaplanır. Önizleme yalnızca hazırlanacak değişikliği gösterir; çalışma dosyanız değiştirilmez, önceden hazırlanmış içerik korunur. Farklı sayıda satır içeren değiştirme/silme grupları bölünmeden hazırlanır; önizlemede bunu kontrol edin. Yeni dosyalar önce dosya düzeyinde Git add ile hazırlanmalıdır. Bu araç UTF-8 metin içindir.

**Güncelleme:** Hazır Windows kurulumu için Dosya → Güncelleme paketini uygula menüsünden yeni Windows ZIP dosyasını seçin. Paket arka planda açılıp her dosyanın SHA-256 değeri denetlenir; sonra sürüm bilgisiyle onay istenir. Editör normal kaydetme/kapatma akışından geçer. app/runtime klasörleri değiştirilir; kullanıcı ayarları, kurtarma kayıtları ve kurulum dışındaki projeler korunur. Eski uygulama `.atelier-backup-*` altında kalır. Kopyalama hatasında eski klasörler geri konur; sonuç `update.log` dosyasına yazılır. Paket doğrulaması bozulmayı denetler, yayıncı dijital imzası değildir; yalnızca güvendiğiniz kaynaktan indirdiğiniz paketi seçin. Çevrimiçi sürüm servisi bulunmaz; güncelleme dosyasını kullanıcı seçer. Kaynak sürümü yeni kaynak ZIP dosyasıyla elle güncellenir. v4'ten ilk geçişte eski editörü kapatıp yeni paketin kur.cmd dosyasını çalıştırın.

## Sınırlar

Bu sürüm bir masaüstü editörüdür; tam kapsamlı IDE değildir. Eklenti sistemi ve uzak debugger bağlantısı içermez. Debugger sırasında etkileşimli input() desteklenmez; bu programları F5 ile veya terminalde çalıştırın. Biçimlendirme ve yeniden adlandırma dil sunucusunun sonuçlarına bağlıdır. Harici programların dosyada yaptığı değişiklikler bildirilir, otomatik birleştirilmez.

Proje araması UTF-8 metin dosyalarında çalışır; gizli ortam/cache/build klasörleri, sembolik bağlantılar ve 2 MB üzerindeki dosyalar atlanır. İlk 5000 eşleşme gösterilir. Projede değiştirme bu taramada bulunan dosyaları kapsar. Editörde açma sınırı 25 MB. Git görünümü için Git kurulu ve PATH üzerinde olmalıdır. Git kenar işaretleri kaydedilen içerikle HEAD arasındaki farkı gösterir.

## Nuitka ile Windows x64 build

Windows x64 üzerinde varsayılan derleyici Visual Studio Build Tools ve Windows SDK kullanır. CPython 3.12 ile `--compiler mingw64` seçeneği Nuitka'nın taşınabilir MinGW64 derleyicisini indirir. [Nuitka gereksinimleri](https://nuitka.net/user-documentation/user-manual.html#requirements)

```powershell
python -m pip install -r requirements-build.txt
python build_nuitka.py --dry-run
python build_nuitka.py
```

Çıktı `dist/Atelier/Atelier.exe` altında oluşur. Dağıtım için `dist/Atelier` klasörünün tamamı gerekir. Terminal ve arka plan işleri Atelier ile derlenir. Dil sunucusu ve debugger, seçili Python üzerinden paketteki `support` araçlarını başlatır. Test paneli proje ortamındaki pytest ve coverage'ı kullanır ve gerekirse paketteki sürümlere başvurur. Araçları proje ortamına ayrıca kurmanız gerekmez.

Atelier, projeye kaydettiğiniz bir Python seçimi varsa onu kullanır. Otomatik seçim proje kökündeki `.venv` veya `venv` ile başlar, ardından sistem Python'una bakar. Python bulunamazsa editör açık kalır ve çalıştırma, debugger veya test işlemi istendiğinde uyarı gösterir.

`python build_nuitka.py --release` dağıtım klasörünü `dist/Atelier-9.4.0-windows-x64.zip` olarak hazırlar. Pencere başlığı, Windows dosya ve ürün sürümleri ile ZIP adı `atelier/version.py` dosyasındaki sürümü kullanır. ZIP'i bütünüyle açıp içindeki `Atelier.exe` dosyasını çalıştırın. Ayrı ayarlarla denemek için çalıştırmadan önce `ATELIER_SETTINGS_FILE` ortam değişkenine kullanılacak INI dosyasının tam yolunu verin.

Eski kaynak tabanlı Windows güncelleme biçimi `python -m tools.build_source_distribution <yeni-klasör>` ile hazırlanır.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Entegrasyon testleri Qt, python-lsp-server, autopep8, debugpy, ConPTY/PTY, pytest ve Git ile çalışır. Git yoksa ilgili testler atlanır. Elle deneme akışları `docs/USER_TRIALS.md` içindedir.

## Dosyalar

- `main.py` uygulamayı başlatır. `atelier/app` pencereyi ve özelliklerine göre ayrılmış pencere komutlarını içerir.
- `atelier/editor`, `atelier/languages` ve `atelier/ui` editör bileşenlerini, dil araçlarını ve arayüzü içerir.
- `atelier/projects`, `atelier/storage`, `atelier/search` ve `atelier/git` proje ayarlarını, oturumları, aramayı ve Git işlemlerini yönetir.
- `atelier/debugger`, `atelier/terminal`, `atelier/testing`, `atelier/runtime` ve `atelier/workers` çalıştırma araçlarını ve arka plan süreçlerini içerir.
- `tests` kaynak testlerini, `tools` build ve Windows kurulum yardımcılarını, `docs` doğrulama ve deneme notlarını içerir.

Teknik kaynaklar: [Qt for Python](https://doc.qt.io/qtforpython-6/), [python-lsp-server](https://github.com/python-lsp/python-lsp-server), [debugpy](https://github.com/microsoft/debugpy), [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/overview.html).
