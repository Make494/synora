# Synora

Synora нь 18–24 сартай хүүхдийн хөгжлийн зарим онцлогийг анзаарахад эцэг эхэд туслах, Q-CHAT-10 асуулгад суурилсан Монгол хэл дээрх анхан шатны скринингийн capstone прототип юм.

> **Эмнэлгийн оношилгоо биш.** Оноо нь онош, аутизмын магадлал эсвэл хүүхдийн хөгжлийн эцсийн үнэлгээ биш. Санаа зовж буй зүйл байвал хүүхдийн эмч, холбогдох мэргэжилтэнтэй зөвлөлдөнө үү. Асуултын Монгол орчуулга нь ажлын орчуулга бөгөөд клиникийн хувьд баталгаажсан гэж үзэхгүй.

## Шаардлага

- Windows 11
- Python 3.10 буюу түүнээс хойш
- Эхний хувилбарыг ажиллуулахад Firebase-ийн бүртгэл, ML загвар шаардахгүй.

## Суулгах, ажиллуулах (PowerShell)

```powershell
cd D:\synora
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` файлд `SECRET_KEY`-г урт, санамсаргүй утгаар солино уу. PowerShell дээр санамсаргүй нууц түлхүүр үүсгэх жишээ:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Локал хөгжүүлэлтийн үед Flask debug горимыг идэвхжүүлж серверээ эхлүүлэх:

```powershell
$env:FLASK_DEBUG = "true"
python app.py
```

Вэбсайт: [http://127.0.0.1:5000](http://127.0.0.1:5000)

`FLASK_DEBUG=true`-г зөвхөн локал хөгжүүлэлтэд ашиглана. Бусад орчинд `FLASK_DEBUG=false` байлгаж, `SECRET_KEY`-г орчны хувьсагчаар тохируулна.

## Production deployment

Энэ төсөл WSGI server ашигладаг. Root түвшний `Procfile` нь Gunicorn-д зориулсан start command агуулна; Linux/container/PaaS орчинд `requirements.txt`-ээс dependencies суулгасны дараа ажиллуулна:

```sh
gunicorn --bind 0.0.0.0:${PORT:-8000} app:app
```

`Procfile`-ийг ашигладаг hosting provider-д мөн энэ command тохирно:

```text
web: gunicorn --bind 0.0.0.0:$PORT app:app
```

Provider dashboard-д дараах environment variables-ийг тохируулна:

| Нэр | Шаардлага | Утга/тайлбар |
|---|---|---|
| `APP_ENV` | Заавал | `production`; энэ үед `SECRET_KEY` байхгүй бол app эхлэхээс татгалзаж, debug унтарч, session cookie Secure болно. |
| `SECRET_KEY` | Заавал | Нууц manager-д хадгалах урт, санамсаргүй утга. Репозиторт, image-д эсвэл клиент талд бүү оруул. Жишээ үүсгэх: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `PORT` | Provider-оос | Hosting provider-ийн оноосон порт. Дээрх start command энэ утгыг ашиглана; гараар тогтмол порт оноохгүй. |
| `COOKIE_SECURE` | Production-д шаардлагагүй | Production орчинд үргэлж Secure cookie хэрэглэнэ. Development орчинд HTTPS ашиглавал `true` тавьж болно. |
| `FIREBASE_ENABLED` | Сонголтоор | `false` буюу тохируулаагүй хэвээр үлдээхэд мэдээлэл Firebase-д хадгалагдахгүй. Зөвшөөрөл, өгөгдөл хамгаалалт, үйлчилгээний credentials-ийг бүрэн тохируулсны дараа л `true` болгоно. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Firebase асаасан үед | Hosting provider-ийн нууц хадгалах хэсэгт байршуулсан service account/ADC credential-ийн зам. JSON түлхүүрийг Git-д бүү commit хий. |
| `RESEARCH_MODEL_PATH` | Судалгааны prediction-ийг ажиллуулах үед | Provider-ийн persistent/secure file storage дахь `synora_model.joblib` файлын бүрэн зам. Энэ хувьсагчгүй, эсвэл model файл байхгүй үед зөвхөн судалгааны prediction API `503` буцаана. |
| `CORS_ORIGINS` | Cross-origin клиенттэй үед | API-г дуудах яг зөвшөөрөгдсөн origin-уудыг таслалаар тусгаарлаж тохируул. Same-origin веб хэрэглээнд өөрчлөх шаардлагагүй. |

`/healthz` нь `{"status":"ok"}` буцаадаг энгийн health check. Энэ нь Firebase, model файл эсвэл бусад гаднын үйлчилгээний бэлэн байдлыг батлахгүй.

Firebase анхдагчаар унтраалттай бөгөөд өгөгдөл автоматаар хадгалахгүй. Судалгааны model artifact нь Git-д дагахгүй (`*.joblib` ignore дүрэмтэй); normal assessment workflow-д шаардлагагүй, зөвхөн `/api/research/prediction`-ийг ашиглах тусгай deployment-д provider-ийн хамгаалалттай storage-оос `RESEARCH_MODEL_PATH`-аар холбоно. Model-ийг репозиторт нэмэх эсвэл дахин сургахгүй.

`APP_ENV=production` тохируулсан эсэх, `SECRET_KEY`-г зөвхөн hosting secrets manager-д оруулсан эсэх, `FIREBASE_ENABLED=false` эсэхийг deployment хийхээс өмнө баталгаажуул. GitHub руу push хийх, hosting account руу нэвтрэх, бодит deployment хийх үйлдлийг зөвшөөрөлгүйгээр хийхгүй.

**Бодит хүүхдийн мэдээлэлтэй нээлттэй production үйлчилгээ болгоход хараахан бэлэн гэж үзэж болохгүй.** Flask-ийн default session cookie нь нас, оноо, тайлбарыг client талын cookie дотор гарын үсэгтэй (гэхдээ шифрлээгүй) хадгалдаг. Мөн research prediction endpoint өөрөө нэвтрэлтээр хамгаалагдаагүй. Бодит хэрэглэгч нээхээс өмнө хувийн мэдээллийн эрсдэлийн үнэлгээ хийж, session өгөгдөл хамгаалах шийдэл, research API-ийн access control, consent/retention/deletion ажиллагааг баталгаажуул. Энэ deployment заавар нь hosting-ийг асаах техникийн алхмууд бөгөөд эдгээр шаардлагын оронд хэрэглэхгүй.

## Тест

```powershell
pytest
```

Тестүүд асуулгын оноолол, зөвшөөрөлтэй нэгдсэн урсгал, камер алгасах/боломжгүй төлөв, үр дүнгийн тайлбар, Flask route болон судалгааны API-г шалгана.

## Нэгдсэн үнэлгээний урсгал

- Хэрэглэгч `/assessment` хуудсанд нууцлалтай танилцаж, асран хамгаалагч/эрх бүхий хүний зөвшөөрлийг баталгаажуулж шинэ сесс эхлүүлнэ. Хүүхдийн судалгааны оролцоонд асран хамгаалагчийн зөвшөөрлөөс гадна хүүхдийн нас, хөгжлийн түвшинд тохирсон зөвшөөрөл (assent) авна.
- Дараа нь 18–24 сарын хүүхдийн Q-CHAT-10-ын 10 асуултад хариулна. Q-CHAT-10 хариултыг шалгаж оноог backend тооцон зөвхөн одоогийн Flask session-д үр дүн болгон тавина.
- Асуулгын дараа `/camera` руу үргэлжилнэ. Камерын зөвшөөрөл тусдаа; хэрэглэгч туршилтыг дахин оролдох, алгасах эсвэл боломжгүй гэж тэмдэглэж үр дүн рүү шилжиж болно. Камерын frame, нүүрний зураг, калибровкийн дээж сервер рүү дамжихгүй. Gaze чиглэлийн browser-only тоолол байвал үр дүн хуудсанд түр тойм хэлбэрээр харуулаад sessionStorage-оос цэвэрлэнэ.
- `/results` Q-CHAT-10 болон camera experiment-ийг тусдаа харуулна. Камер алгасах/ажиллахгүй байх нь эрсдэлийн үзүүлэлт биш. Одоогийн gaze estimate-ийг Q-CHAT-10-тай ижил screening indicator гэж үзэх баталгаажсан арга байхгүй тул эх сурвалжуудын нийцэл, зөрүүг дүгнэхгүй.
- 1–10-ийн UI ангилал (1–2 маш бага, 3–4 бага, 5–6 дунд, 7–8 өндөр, 9–10 маш өндөр) нь туршилтын placeholder. Баталгаажсан оноолтын арга хүртэл нэгтгэсэн оноо `— / 10` хэвээр; Q-CHAT-10 эсвэл gaze хэмжилтээс нэгтгэсэн оноо гаргахгүй.
- Асуултын Монгол текст ба хариултууд `data/questions_mn.json` файлд, вэбийн кодоос тусдаа байна.
- Оноог зөвхөн Flask backend тооцно. 1–9-р асуултад A/B=0, C/D/E=1; 10-р асуултад A/B/C=1, D/E=0.
- 0–2 оноо нь лавлагааны босго оноонд хүрээгүй, 3–10 нь хүрсэн гэж тайлбарлагдана. Аль ч үр дүн нь оношилгоо биш.
- Сессэд зөвхөн үр дүнг харуулахад шаардлагатай оноо, нас, тайлбарыг хадгална. Хариултыг браузерын санах ойгоос өөр байнгын хадгалалтад хийхгүй (Firebase-ийг зөвшөөрөлтэйгөөр зориуд идэвхжүүлээгүй тохиолдолд).
- Харагдах navigation-д камер, feature гараар оруулах хуудас ороогүй. `/research` нь өмнөх хяналттай developer туршилтын хуудас хэвээр байгаа; энгийн үнэлгээний алхам биш.

## Firebase Firestore (сонголтоор)

Эхний хувилбарт Firebase идэвхгүй. Хадгалалтыг асаахаас өмнө хэрэглэгчийн зөвшөөрөл, өгөгдөл устгах хүсэлт боловсруулах ажиллагаа, төслийн өгөгдөл хамгаалалтын хариуцлагыг тодорхой тохируулна уу.

1. Firebase төсөлдөө Firestore идэвхжүүлж, `firestore.rules`-ийг байршуулна уу. Клиент талын шууд уншилт/бичилт хаалттай.
2. Сервер ажиллах орчинд зөвшөөрөлтэй service account эсвэл Application Default Credentials тохируулна. Нууц түлхүүрийг репозиторт эсвэл frontend-д бүү оруул.
3. Орчны хувьсагч тохируулна:

   ```powershell
   $env:FIREBASE_ENABLED = "true"
   $env:GOOGLE_APPLICATION_CREDENTIALS = "D:\secure\synora-service-account.json"
   ```

4. Эцэг эх үнэлгээний хуудсан дээрх хадгалалтын зөвшөөрлийг сонгосон үед л нас, 10 хариулт, оноо, зөвшөөрөл болон серверийн timestamp Firestore-д хадгалагдана. Нэр, төрсөн огноо, хаяг, утасны дугаар цуглуулахгүй.
5. Хадгалсан өгөгдлийг устгуулах хүсэлт хүлээн авах холбоо барих сувгийг үйлчилгээг нээхээс өмнө төслийн эзэмшигч тохируулна. Энэ код өөрөө хүсэлтийн тусгай inbox нэмээгүй.

Хадгалалтыг шалгахдаа Firebase credential-гүй local орчинд `FIREBASE_ENABLED=false` хэвээр байлгана. Тохиргоо идэвхтэй боловч серверийн credentials буруу бол зөвшөөрөл өгсөн хадгалалт алдаатай дуусч, API `503` буцаана.

## ML судалгааны API ба scaffold

`/api/research/prediction` нь хяналттай хөгжүүлэлт болон тестийн үед л ашиглах судалгааны endpoint. Энэ нь `/research` хуудсанд байсан зургаан numeric feature-ийг хүлээн авдаг боловч энгийн хэрэглэгчийн нэгдсэн урсгалд гараар feature асуухгүй, prediction дууддаггүй. Browser-ийн одоогийн gaze тойм нь загварын feature-тэй яг таарах тодорхойлолт, тооцоолол биш тул уг загварыг хэрэглэгчийн үнэлгээнд холбохгүй.

Одоогийн анхны хувилбарт тохирох, эрхтэй, мэргэжлийн хувьд үнэлэгдсэн dataset хавсаргаагүй. Иймээс дахин сургалт эсвэл эмнэлзүйн ангилал хийхгүй. Scaffold-ийг зөвхөн ашиглах зөвшөөрөлтэй, `q1`–`q10` баганатай CSV болон 0/1 хоёр ангиллын зорилтот баганатай үед ажиллуулна:

```powershell
python -m ml.train_model --dataset "D:\data\authorized.csv" --target-column label --authorized-dataset
```

Нэг хүүхдийн олон мөр байж болох бол хүүхдийн тогтвортой таних бүлгийн баганыг заавал өгч, хүүхдээр бүлэглэсэн хуваалт хэрэглэнэ:

```powershell
python -m ml.train_model --dataset "D:\data\authorized.csv" --target-column label --group-column child_group --authorized-dataset
```

Pipeline нь preprocessing-ийг зөвхөн сургалтын өгөгдөлд fit хийж, тестийн precision, recall, F1 болон confusion matrix-ийг тайлагнана. Үр дүн нь туршилтынх бөгөөд клиникийн хэрэглээнд зориулагдаагүй. Зөвшөөрөл, мэргэжлийн review, хараат бус баталгаажуулалт хийгдээгүй загварыг эцэг эхэд таамаглал болгон харуулахгүй.

`data/synora_model.joblib` нь `model`, `features`, `classes`, `purpose` түлхүүртэй хадгалсан судалгааны bundle; энэ ажлын явцад файл өөрчлөгдөөгүй. `ml/predict.py` нь `tracking_ratio`, `ball_visible_rate`, `pointing_rate`, `eyes_rate`, `face_rate`, `Age` гэсэн зургаан numeric feature-ийг bundle-д хадгалсан дарааллаар ашиглана. Одоогийн browser gaze/calibration систем эдгээрийн анхны measurement definitions-ийг гаргадаггүй тул `/results`-д ML prediction боломжгүй гэж тэмдэглэнэ. Endpoint-ийг хяналттай туршилтад ашиглах бол бодит, эрхтэй, анхны тодорхойлолтод нийцсэн feature хэмжилт шаардана. Үр дүн нь эмнэлзүйн онош биш.

## Browser camera болон нүүрний landmark туршилт

`/camera` хуудсанд Chrome-ийн суурилуулсан камер эсвэл USB webcam-ийг сонгож, MediaPipe Face Landmarker-ээр нүүрний цэгүүдийг browser дотор дүрсэлнэ. Камер асахаас өмнө хэрэглэгчийн зөвшөөрөл шаардана. Видео/нүүрний дүрсийг Flask руу явуулахгүй, серверт хадгалахгүй, бичлэг хийхгүй; камер ашиглахын тулд HTTPS эсвэл `localhost` шаардлагатай. Хүүхэд оролцох судалгаанд асран хамгаалагчийн зөвшөөрөл болон хүүхдийн оролцох зөвшөөрлийг урьдчилан авна.

- JavaScript багц: `@mediapipe/tasks-vision` **1.2.0**, jsDelivr дээр хувилбарыг тогтоосон browser bundle: `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.0/vision_bundle.mjs`. WebAssembly файлууд ижил хувилбарын `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.0/wasm` замаас ачаална. Эх сурвалж: [MediaPipe Face Landmarker for Web](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js), [npm багц](https://www.npmjs.com/package/@mediapipe/tasks-vision).
- Model asset: Google MediaPipe-ийн `face_landmarker` float16 хувилбар 1: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` (эх сурвалж: [Face Landmarker загварууд](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/index#models)).
- Эхлээд GPU delegate хэрэглэж, үүсгэж чадахгүй бол CPU delegate рүү шилжинэ. Face Landmarker-ийн синхрон видео боловсруулалт нь төхөөрөмжийн хүчин чадлаас хамааран browser UI-г саатуулж болно.
- Нүдний хүрээний харагдах landmark-ууд: 33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246 болон 362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382. Iris төвийг 468–472 болон 473–477 багцын цэгүүдийн дунджаар тооцно. Хоёр нүдний iris төвийг тухайн нүдний хүрээний bounding box-д нормчилж, урд камерын толин тусгалын чиглэлд ойролцоогоор зүүн/баруун/дээш/доош/төв болгон харуулна. Дутуу, давхцсан эсвэл хүрээнээс гадуур цэгийг хүчинтэйд тооцохгүй.
- 5 цэгийн калибровк нь төв ба дөрвөн булангийн байршил бүрд 8 хүчинтэй кадрын дээж цуглуулж, browser memory-д affine зураглал тааруулна. Face эсвэл хоёр нүдний landmark найдвартай биш үед дээж авахгүй. Калибровк нь хуудсыг хаах, камерыг зогсоох эсвэл төхөөрөмж солиход арилна; сервер/localStorage-д хадгалахгүй.
- Энэ gaze нь iris-ийг eye-boundary хүрээнд харьцуулсан туршилтын ойролцоо heuristic. Нарийвчлал нь хэмжигдээгүй, эмнэлзүйн баталгаатай биш. Gaze чиглэл, fixation duration, оношилгоо, ASD prediction хийхгүй; tracking тасрахыг зан үйл/эрүүл мэндийн шинж гэж тайлбарлахгүй. Accuracy хувь тооцохгүй.

Камерын төхөөрөмж байхгүй эсвэл browser permission олгоогүй үед хуудсыг `localhost` дээр нээгээд Chrome-ийн камерын зөвшөөрлийг шалгана. Model болон runtime CDN/Google-оос татагдах тул эдгээр домэйнд зөвхөн статик JavaScript/WASM/model хүсэлт очно; камерын дүрсийг сүлжээгээр илгээхгүй.

Gaze helper-ийн unit тестийг Node.js суулгасан үед ажиллуулна:

```powershell
node --test tests/gaze.test.mjs
```

## Төслийн credits

Төслийг санаачлагчид:

- Нандин-Эрдэнэ
- Мөрөөдөл

AI модель сургаж, систем хөгжүүлсэн:

- А. Малик
