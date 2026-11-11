# Doğrulama sonucu

Proje güveni ve çoklu terminal: Sekiz farklı hedefli kaynak testi geçti. İlk açılış penceresinde Kısıtlı aç seçimi kaydedildi. Kısıtlı projede dosya açma, kaydetme ve arama çalıştı. LSP ve terminal başlatılmadı, Çalıştır, proje görevleri, testler ve Git engellendi. Güven verildiğinde LSP ve terminal başladı, güven kaldırıldığında durdu. Bağımsız terminal sekmeleri ayrı süreçlerde çalıştı; proje değiştirip dönünce mevcut oturumlar korundu. Yeni Windows ZIP'i oluşturulmadı.

9.4.0 Windows x64 sürümü: Beş kaynak testi geçti (32,010 saniye). Araç çubuğundan seçilen profil Çalıştır ve Debug'a aynı dosya, dizin ve argümanları iletti. Komut isteminde bekleyen Windows terminali yeni `.venv` ile açıldı; komut çalışırken süreç korundu. `requirements.txt` ve `pyproject.toml` kurulumları yerel paketlerle geçti. Derlenmiş ZIP Türkçe karakterli bir yola çıkarıldı; arşiv bütünlüğü, EXE sürümü, terminal ve LSP'nin proje `.venv`'siyle otomatik başlaması ve derlenmiş terminalde komut çalıştırma doğrulandı. Profil seçimi ve ortam kurulumunun arayüz akışları kaynak testleriyle sınandı.

Proje hazırlama ve terminal güncellemesi: Beş hedefli kaynak testi geçti (31,471 saniye). Kurulum onayı iptal edildiğinde `.venv` oluşturulmadı. Onaylandığında yerel deneme paketi önce `requirements.txt`, ardından mevcut ortamda `pyproject.toml` üzerinden kuruldu. Ortamın seçilmesi ve LSP'nin yeniden başlaması doğrulandı. Çalıştır ve Debug aynı dosya, çalışma dizini ve argümanları aldı. Terminal açılışta hazırdı ve sekme gösterildiğinde aynı süreçle devam etti. Yeni ZIP oluşturulmadı.

9.3.0 Windows x64 sürümü: Derlenmiş ZIP, temiz ayar profilleriyle üç durumda açıldı. Python'un PATH ve kayıt defteri üzerinden keşfedilemediği süreçte editör açık kaldı. PATH'te yalnızca sistem Python'u olduğunda LSP onunla başladı. Temel Python klasörü silinmiş bir `.venv` olduğunda LSP yine sistem Python'uyla başladı. Kaynak testinde panelin eksik temel Python yolunu, yorumlayıcı sürümünü ve LSP çıkış kodunu gösterdiği, yeniden başlatma düğmesinin bağlantıyı geri getirdiği doğrulandı. Python yokken Çalıştır, Debug ve test uyarıları yeniden doğrulandı. ZIP bütünlüğü ve kopya dosyanın özeti kontrol edildi.

9.2.0 Windows x64 sürümü: Nuitka ZIP'i 63.727.996 bayt. Arşiv bütünlüğü ve üst düzey `runtime` klasörünün kaldırıldığı doğrulandı. Türkçe karakterli ve boşluk içeren yollarda derlenmiş uygulama, temiz proje `.venv`'sini otomatik seçip LSP'yi başlattı. Aynı ZIP'ten çıkan araçlarla, ek paket kurulmamış Python ortamında projeye özel modülün tamamlanması, hata uyarısı, debugger kesme noktası, pytest ve kapsam raporu geçti. Derlenmiş terminal ve JSON doğrulama, sistem Python'u arama yolundan çıkarıldığında çalıştı. Python bulunmadığında editörün açık kaldığı ve Çalıştır, Debug ve testlerin uyarı verdiği kaynak testinde doğrulandı.

9.1.0 Windows x64 sürümü: `Ctrl+Tab`, Ctrl basılıyken birden çok sekmeye geçiş, ters sıra ve `Ctrl+Shift+T` ile sekme konumu ve imlecin geri gelmesi kaynak testinde geçti. `python build_nuitka.py --release --compiler mingw64` ile ZIP üretildi. Arşiv bütünlüğü, 7.878 dosyanın paket yerleşimi ve EXE'nin Windows dosya/ürün sürümü (9.1.0.0) doğrulandı. Derlenmiş EXE ve içindeki dil sunucusu, Türkçe karakterli kurulum ve proje yollarında, ayrı bir INI profili ve yalnızca Windows dizinlerini içeren PATH ile açıldı. Tamamlama, hata uyarıları, terminal komutu, debugger kesme noktası ve pytest için kaynak arayüzle, aynı ZIP'ten çıkarılan Python çalışma ortamı kullanıldı. Ayrı bir Windows sanal makinesinde test yapılmadı.

Paketlere ayırma ve son projeler değişikliği: 43 kaynak testinin ilk turunda 42 test geçti. Son projeler senaryosunun kontrolleri tamamlandı, ancak Windows geçici proje klasörünü kaldırırken erişim hatası verdi. Test sonunda Qt pencere nesnesi serbest bırakıldı. Son projeler, proje geçişi ve oturum kurtarma testlerinin üçü de tekrar çalıştırıldığında geçti. Pyflakes, Nuitka `--dry-run` ve dağıtım klasörüne yerleştirilen yardımcı betiğin başlatılması doğrulandı. Nuitka derlemesi yapılmadı.

11 Kasım 2026, v9: 34 farklı kaynak testi geçti; bazı senaryolar düzeltmeden veya test ortamı hazırlandıktan sonra yeniden çalıştırıldı. İlk 31 testlik turda 29 test geçti (452,128 saniye). Git farkı testi Windows atomik değiştirme çağrısında geçici erişim hatası gördü. Sınırlı yeniden deneme eklendi; dosya bu arada dışarıdan değişirse kayıt durur. Son dört hedefli test, bu iki durumu taklit eden test dahil, geçti (22,222 saniye). İlk turdaki diğer başarısız test, eski gömülü Python'da coverage bulunmayan kapsam testiydi; bağımlılıkların bulunduğu ayrı kaynak test ortamında kapsam ve pytest paneli geçti (15,841 saniye). v8 Python ortamı/paket testlerinin ikisi de geçti (38,503 saniye).

- Gerçek geçici Git deposunda iki `diff3` çakışması çözüldü. Çözülmemiş sonuç hazırlanmadı, iptal edilen kayıtta editör geri alındı, son çözüm Git dizinine yazıldı.
- Kayıt otomasyonunda import sıralama, biçimlendirme, çok satırlı dizgi içindeki boşlukların korunması, dört dosyanın kuyruklanması ve eski sonucun yeni düzenlemeye/disk içeriğine uygulanmaması kontrol edildi.
- Sembol araması kaydedilmemiş sınıf/metot tanımına gitti. Takılan regex araması durduruldu ve sonraki arama sonuç verdi. 22.000 satırı aşan belgede minimap, katlama, renklendirme ve LSP devre dışı kalırken düzenleme/kayıt çalıştı.
- Gerçek debugger'da koşullu kesme noktası, çalışan satır vurgusu, fareyle değişken değeri ve devam etme doğrulandı. Kararlılık turunda sekmeler ve bölünmüş görünümler hızla açılıp kapatıldı, dil sunucusu yeniden başlatıldı, dışarıdan silinen dosyanın içeriği korundu. Sekme ve boyut değişiklikleri sırasında sekiz komut aynı terminal sürecinde çalıştı; boşta yeniden çizim tekrarlanmadı.
- Çakışma ekranı açık/koyu temada görüntülendi. Derleme veya dağıtım paketi oluşturulmadı.

v8 kaynak güncellemesi: iki yeni entegrasyon testi geçti (40,833 saniye). Gerçek geçici venv oluşturma ve pip hazırlığı; ortam keşfi, proje bazında seçim/kalıcılık, LSP'nin yeniden bağlanması ve seçili Python ile program çalıştırma doğrulandı. Yerel test wheel'i requirements dosyasından kuruldu, paket listesi/filtrelemesi, freeze ile dışa aktarma, pip check ve kaldırma gerçek pip süreçleriyle geçti. Var olan ortam klasörünü koruma, paket adı/sürümü doğrulama, süreç durdurma, hatalı çıkış ve bulunamayan Python sonrası arayüzün açılması kontrol edildi. Ağdan kurulum/güncelleme yapılmadı; uzak depo erişimi ayrıca kullanıcı ortamına ve ağa bağlıdır. Mevcut v7 import/refactor/imza/geçmiş/çalıştırma profili regresyon testi de geçti (6,470 saniye). Yeni ekran açık/koyu temada görsel olarak kontrol edildi. Derleme veya dağıtım paketi oluşturulmadı.

v7 kaynak güncellemesi: debugger regresyon testi ve iki yeni kaynak testi geçti (toplam 17,127 saniye). Import önerme/düzenleme, fonksiyon/değişken çıkarma, imza seçimi/aktif parametre, geçmiş, çalışma dizini/argüman/ortam değişkenli profil, traceback konum çözümü, çoklu dosya seçimi/silme çağrısı ve kısayol alanı yüksekliği kapsandı. Terminal aynı süreç kimliğiyle açık kaldı; yinelenen boyut isteklerinden sonra boşta yeniden çizim döngüsü oluşmadı. Arka plan çıktısının terminal sekmesini değiştirmediği son ek test de geçti (5,212 saniye). v6'nın üç hedefli testi ayrıca geçti (19,608 saniye). Geri dönüşüm kutusu çağrısı taklit edildi; kullanıcı dosyaları silinmedi. Terminal gerçek Windows kabuğuyla doğrulandı. Derleme/paketleme yapılmadı.

v6 kaynak güncellemesi: üç hedefli kaynak testi geçti (22,855 saniye). Çoklu imleç/geri alma, regex değiştirme, Ctrl+P dosya araması, ayarların uygulanması, logo, proje filtresi, hızlı düzeltme istemcisi, gerçek pytest/coverage ölçümü ve Git grubunu hazırlama/hazırlamadan çıkarma doğrulandı. Hızlı düzeltme için LSP yanıtı taklit edildi; uygulanacak düzeltmeler gerçek sunucunun yeteneklerine bağlıdır. Logo yüklendi ve pencere ikonu boş değil. Derleme veya paketleme yapılmadı. Aşağıdaki kayıtlar önceki sürümün test geçmişidir.

10 Kasım 2026, v5: Hazır Windows paketindeki Python 3.14.10 ile 21 entegrasyon testi geçti (147,449 saniye). Son dosya-yolu korumaları için dosya/refactor testi ayrıca geçti (5,934 saniye); dosyalar arası F12 geri dönüşünü de içeren proje/gezinme testi ayrıca geçti (8,430 saniye).

Test ortamı: Windows x64, Python 3.14.10, PySide6-Essentials 6.12, python-lsp-server 1.15, debugpy 1.8.22, autopep8 2.3.2, Markdown 3.11.3, pyte 0.8.2, pywinpty 3.1.2 ve pytest 9.2. Qt testleri ekran açmadan çalıştırıldı; dil sunucusu, debugger, ConPTY terminali ve Git gerçek süreçler olarak kullanıldı. Geliştirme sırasında Python 3.12 üzerinde de önceki 10 testin tamamı geçti.

v5 ek bağımlılıkları: QtAwesome 1.4.2 (Material Design Icons/mdi6), Send2Trash 2.1.0 ve Rope 1.15.2.

| Kontrol | Sonuç |
|---|---|
| Yazarken ve Ctrl+Space ile tamamlama, öneri ekleme, hata çizgileri, paylaşılan bölünmüş editör, parantez/girinti/yorum, satır numaraları | Geçti |
| Kesme noktasında durma, çağrı yığını, değişkenler, adımlama ve devam ederek programı tamamlama | Geçti |
| Git farkı, satır işaretleri, alt klasördeki yeni dosyanın doğru adresle listelenmesi | Geçti |
| Tanıma gitme, hover, parametre imzası, sembol yeniden adlandırma, biçimlendirme, kayıt ve LSP ortamını yeniden bağlama | Geçti |
| Dosyada/projede arama ve değiştirme, program çalıştırma, açık/koyu tema, yazı boyutu ve Python dışı dosyaların LSP dışında tutulması | Geçti |
| Fonksiyon/metot/sınıf önerisinde parantez ekleme, imleci içine yerleştirme, var olan parantezi koruma ve import istisnası; gerçek LSP ile len() | Geçti |
| Markdown renklendirme, canlı belge önizlemesi, HTML kaynağı, tablo ve fenced code | Geçti |
| Dosyanın dışarıda değişmesi/silinmesi, yeniden yükleme, yerel içeriği koruma, üzerine yazmayı iptal etme ve kendi kaydını ayırma; kod katlama ve minimap | Geçti |
| Kalıcı ConPTY terminalinde komut, etkileşimli Python REPL, 6 * 7 çıktısı ve shell'i kapatma | Geçti |
| Git stage/unstage, yeni dosyayı koruma, commit ve geçmiş | Geçti |
| Yerel bare Git deposunda push/pull, dal oluşturma ve geçmiş görünümü | Geçti |
| def şablonunu Tab ile genişletme, alanlar arasında gezinme ve komut paletinden eylem çalıştırma | Geçti |
| Kaydedilmemiş içeriği kurtarma; etkin belge, imleç, bölünmüş görünüm, kesme noktaları/koşulları ve izlenen ifadeler; QSettings maximized/gizli panel/geometry | Geçti |
| Test panelinde pytest keşfi, tümünü/seçileni çalıştırma, geçen/kalan sonuçlar ve hatalı satıra navigasyon | Geçti |
| i == 2 koşulunda debugger durması, watch ifadesi ve değişkeni düzenleyerek watch değerinin güncellenmesi | Geçti |
| Git init düğmesi, izlenmeyen/hazırlanmış/karma durumlar için proje ağacı renkleri | Geçti |
| 20.000 satırda artımlı renklendirme, kaydırmada minimap önbelleği, değişmeyen dosyada hash atlama, iç içe blok kılavuzları ve bütün simge adlarının yüklenmesi | Geçti |
| Proje bazlı Python/çalıştırma/test tercihleri, referanslar, semboller ve dosyalar arası geri/ileri gezinme | Geçti |
| Dosya/klasör oluşturma, açık belgenin yolunu izleyerek yeniden adlandırma, importları güncelleyen modül refactor'u, geri dönüşüm kutusu çağrısı ve proje dışı hedef koruması | Geçti |
| Seçili satırları index'e hazırlama; seçilmeyen satırların, çalışma dosyasının ve daha önce hazırlanmış içeriğin korunması | Geçti |
| Güncelleme manifesti, bütün dosyaların hash'leri, bozuk paket ve klasör dışına çıkmaya çalışan ZIP yollarını reddetme | Geçti |
| Windows güncelleme yardımcısının eski uygulamayı yedeklemesi ve başarısız kopyalamada önceki klasörleri geri koyması; kullanıcı ayarlarının korunması | Geçti |

Performans ölçümü: başsız Qt testinde 20.000 satır yaklaşık 2,080 saniyede yüklendi; tek satır düzenlemesinde yalnızca 1 blok yeniden renklendirildi. Bu bir donanım bağımsız hız garantisi değildir. Kütüphane/platform sınırı olan geri dönüşüm kutusu çağrısı testte taklit edildi; kullanıcıya ait gerçek dosyalar silinmedi. Güncelleme klasör geçişi/geri dönüş testi geçici kurulumlarda ve yeniden başlatma kapalı olarak çalıştırıldı.

Windows kurulum betiği çalışma klasöründeki ayrı bir hedefe, kullanıcı masaüstü kısayollarını değiştirmeden kuruldu. Kurulan runtime/pythonw.exe üzerinden açılış, LSP bağlantısı ve örnek programı çalıştırma doğrulandı (çıkış kodu 0). Varsayılan kullanıcı klasörüne kurulum ve masaüstü kısayolu oluşturma, kullanıcının sistemini değiştirmemek için otomatik testte uygulanmadı. Python arşivinin SHA-256 değeri resmi Python.org sürüm sayfasındaki değerle doğrulandı.

Arayüz ekran görüntüleri ayrıca incelendi; araç çubuğu, sekmeler, proje ağacı, satır numaraları, kod alanı, minimap, çıktı paneli ve yan yana Markdown önizlemesinin yerleşimi kontrol edildi. Uzak Git hesabı/kimlik doğrulaması ve Unix PTY çalışması bu Windows ortamında denenmedi. Bu testler bütün olası proje/işletim sistemi durumlarını kapsamaz; bilinen sınırlar README.md dosyasında açıklanmıştır.

Gerçek insan kullanıcılarından geri bildirim toplama bu oturumda yapılmadı; otomatik örnek proje akışları, görsel QA ve USER_TRIALS.md kabul senaryoları sağlandı.
