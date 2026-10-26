# Home Assistant для homelab

Власний образ [Home Assistant Container](https://www.home-assistant.io/installation/linux#install-home-assistant-container) для розгортання через **Dokploy** (Docker Compose).

В образ під час **build** включено дві інтеграції з фіксованими версіями:

| Інтеграція | Версія | Призначення |
| --- | --- | --- |
| [EcoFlow Cloud](https://github.com/tolwi/hassio-ecoflow-cloud) | 1.7.2 | EcoFlow River 2 через хмару |
| [Beszel](https://github.com/cgfm/Beszel-HASS) | 1.2.1 | Метрики наявного Beszel Hub |

HACS **не потрібен** для цих інтеграцій і не встановлюється. Під час старту локальний init-скрипт копіює вже зібрані інтеграції до `/config/custom_components`. Жодних завантажень із GitHub під час старту Home Assistant.

## Важливо перед першим деплоєм

**Не створюй другий Home Assistant паралельно з чинним.** У тебе вже працює контейнер `homeassistant`. Потрібно **оновити його чинну Compose-конфігурацію в Dokploy**, а не запускати ще один сервіс із такою самою назвою.

**Збережи наявний `/config`!** Там користувачі, авторизації та налаштування. Перед заміною образу зроби резервну копію цього тому на інший диск / пристрій.

Перевір реальний mount на Debian:

```bash
docker inspect homeassistant --format '{{range .Mounts}}{{if eq .Destination "/config"}}{{.Type}} | {{.Name}} | {{.Source}}{{end}}{{end}}'
```

- Якщо це `volume`, скопіюй **точне** значення `Name` у змінну `HA_CONFIG_VOLUME` у Dokploy. Наведений `compose.yaml` використовує **external volume** та навмисно не створить порожній том при помилці в назві.
- Якщо це `bind`, не використовуй цей Compose без адаптації: заміни монтування `ha_config:/config` на **той самий наявний абсолютний шлях** `/existing/host/path:/config`, а декларацію `ha_config` унизу прибери.

## Деплой через Dokploy

1. Відкрий **існуючий** Docker Compose-сервіс Home Assistant у Dokploy.
2. Прив'яжи Git-репозиторій `MrBelix/home-assistant`, гілку `main`, Compose Path: `./compose.yaml`.
3. Якщо `/config` — Docker volume, у **Environment** задай `HA_CONFIG_VOLUME` зі значенням з команди вище. У Dokploy може бути змінна `HA_CONFIG_VOLUME=...` у конфігурації середовища сервісу.
4. Переконайся, що застосунок має доступ до Docker build у режимі **Docker Compose**, а не Swarm **Stack**.
5. Зроби резервну копію `/config`, лише потім виконуй **Deploy**.
6. Відкрий Home Assistant: `http://<IP-сервера>:8123`. Перевір **Settings → Devices & services → Add integration**.

> Мережа `network_mode: host` використовує порт 8123 хоста; окремі `ports:` не потрібні. Не публікуй Home Assistant напряму в інтернет без захисту.

## Налаштування після деплою

**EcoFlow:** Settings → Devices & services → Add integration → **EcoflowCloud**. Для River 2 можна вибрати `private_api` (неофіційний API EcoFlow App), увійти через свій EcoFlow акаунт. Для європейського акаунта за потреби: `api-e.ecoflow.com`. Пристрій має бути онлайн у EcoFlow App.

**Beszel:** Settings → Devices & services → Add integration → **Beszel**. Якщо Beszel Hub опублікований на Debian порту 8090 і Home Assistant використовує `network_mode: host`: Host = `127.0.0.1`, Port = `8090`, HTTPS = off. Використай Beszel логін і пароль. Перевір, що Hub справді доступний на цьому порту.

Авторизацію в EcoFlow та Beszel виконуємо **один раз через UI**, вона зберігається в `/config`, а не в Git. Паролі й токени **ніколи не комітимо**.

## Homelab dashboard (Server + EcoFlow)

Під час старту образ синхронізує розділені YAML-файли дашборда до `/config/dashboards/`. У дашборді є дві вкладки:

- **mi-server** — CPU, RAM, диски, температура, батарея ноутбука, мережа, uptime, історія навантаження. Використовуються фактичні entity_id з твого Beszel.
- **EcoFlow** — заряд, вхідна/вихідна потужність, залишок часу, здоров'я батареї, доступні AC/DC перемикачі й графік потужності. Entity ID автоматично знаходяться в реєстрі Home Assistant за інтеграцією `ecoflow_cloud`, тож їх не треба вручну копіювати.

Дашборд у звичайній конфігурації з'явиться в боковому меню **Homelab** після успішного деплою та перезапуску Home Assistant.

Якщо `configuration.yaml` ще **не** містить власного ключа `lovelace:`, стартовий скрипт додасть декларацію YAML-дашборда одноразово, зберігши резервну копію `/config/configuration.yaml.before-homelab`. Він не змінює наявні користувацькі налаштування Lovelace.

Якщо `lovelace:` уже є, реєстрацію навмисно пропущено, щоб не перезаписати налаштування. Додай вручну під наявне `lovelace.dashboards`:

```yaml
homelab-server:
  mode: yaml
  filename: dashboards/homelab.yaml
  title: Homelab
  icon: mdi:server
  show_in_sidebar: true
```

Після додавання нових EcoFlow-пристроїв потрібен **перезапуск Home Assistant**, щоб регенерувати список сутностей у вкладці EcoFlow. Ручні зміни у згенерованому файлі `/config/dashboards/homelab.yaml` будуть перезаписані при наступному запуску — змінюй Git-шаблон і скрипт натомість.

Рекомендовано зробити резервну копію `/config` перед деплоєм; це також захистить збережені авторизації EcoFlow та Beszel.

### Графік відключень світла

У вкладці **EcoFlow / Power** є `Історія відключень · останні 72 години` — графік датчика **AC In Volts** на EcoFlow River 2. Для RIVER_2 EcoFlow Cloud надає цей показник (`inv.acInVol`); значення `entity_id` знаходиться автоматично через реєстр інтеграції. Якщо датчик не виявлено або він вимкнений, картка з ним буде пропущена.

- Близько **230 В** — напруга на AC-вході EcoFlow присутня.
- **0 В** — напруга на вході зникла. Це дозволяє бачити моменти й тривалість відключень за умови, що станція постійно під'єднана до тієї самої мережі.
- `unavailable` або розрив графіка — **немає достовірних даних**, а не автоматично відключення світла.
- Графік сам по собі не доводить загальнобудинкове відключення: якщо EcoFlow від'єднати від розетки, AC-вхід також дорівнюватиме нулю.

Історію зберігає Home Assistant Recorder; повні історичні дані можуть бути обмежені його періодом зберігання. Графік поповнюється після увімкнення станції та інтеграції, минулі невідомі відключення не відновлюються.

### Окремі YAML-конфіги вкладок

Вихідна конфігурація більше не є одним великим файлом. В Home Assistant використовуються нативні `!include` директиви:

```yaml
# dashboards/homelab.yaml
title: Homelab
views:
  - !include views/server.yaml
  - !include views/ecoflow.yaml
```

- `dashboards/views/server.yaml` — усі картки Debian-ноутбука `mi-server`. Це звичайний YAML, його можна змінювати незалежно.
- `dashboards/views/ecoflow.yaml` — окремі картки River 2. Значення `@ecoflow_*` у `entity` — це читабельні placeholders, які стартовий скрипт підставляє з реєстру Home Assistant. Якщо сенсор недоступний, відповідна картка приховується.
- `dashboards/homelab.yaml` — лише назва та список вкладок.

З Docker-образу файли потрапляють у `/config/dashboards/`. Головний YAML розбирає сам Home Assistant через `!include`. Лише `views/ecoflow.yaml` перетворюється на конфіг із реальними `entity_id` під час запуску контейнера; збережені облікові дані не зачіпаються.

Для зміни вигляду вкладок редагуй файли в Git, а не згенерований `/config/dashboards/views/ecoflow.yaml`. Після зміни в Git роби Deploy у Dokploy.

## Контроль живлення ноутбука (Power)

Система використовує **локальний** датчик `/sys/class/power_supply/ADP0/online` на Debian-хості `mi-server`. Він уже читається з контейнера Home Assistant. Жодного EcoFlow для виявлення відключень не потрібно.

- `packages/mi_server_power.yaml` — `binary_sensor.mi_server_ac_power` через `command_line` (перевірка кожні **10 секунд**) і статистика `history_stats`: `sensor.mi_server_no_ac_hours_today` та `sensor.mi_server_no_ac_periods_today`.
- `dashboards/views/power.yaml` — стан зовнішнього живлення, батарея ноутбука, години / періоди без адаптера сьогодні й графік за 24 години.
- `scripts/register-power-package.py` — під час старту копіює конфіг у `/config/packages/mi_server_power.yaml` і, лише якщо це безпечно, додає `homeassistant.packages: !include_dir_named packages` до поточного `configuration.yaml`. Перед зміною створює `configuration.yaml.before-power-monitor`.

Якщо в `configuration.yaml` уже є `homeassistant.packages` із нестандартним шляхом або непростий спосіб підключення `homeassistant:`, скрипт **не переписує** його. Перевір повідомлення в логах і додай вручну, якщо треба:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Після Deploy перевір **Developer Tools → States**: `binary_sensor.mi_server_ac_power` має бути `on` (адаптер підключено), `off` (адаптера немає) або `unavailable` (помилка читання). Значення `unavailable` **не є** відключенням світла. Не випробовуй вручну без потреби: достатньо перевірки стану після деплою.

**Увага:** сенсор відображає *наявність живлення на адаптері ноутбука*, а не гарантовано стан міської мережі. Якщо зарядний пристрій підключено через UPS, він покаже `on` навіть під час відключення світла. Home Assistant і сам ноутбук мають бути увімкнені для збору історії. Періоди, коли ноутбук вимкнений, не вимірюються.

## Оновлення

Версії сторонніх інтеграцій закріплено commit SHA у `Dockerfile`. Для оновлення зміни відповідні `ARG`, перевір релізи та зроби новий деплой. Перезапуск контейнера також синхронізує код інтеграцій з образу, тож **не оновлюй ці дві інтеграції через HACS** — наступний запуск перезапише їх код.

Тег базового Home Assistant за замовчуванням — `stable`, він може змінюватися з часом. Якщо потрібна повна повторюваність, зафіксуй конкретний версійний тег або digest базового образу.

## Структура

```text
.
├── Dockerfile
├── compose.yaml
├── dashboards/
│   ├── homelab.yaml
│   └── views/
│       ├── server.yaml
│       ├── power.yaml
│       └── ecoflow.yaml
├── packages/
│   └── mi_server_power.yaml
├── .env.example
├── .dockerignore
└── scripts/
    ├── sync-integrations.sh
    ├── register-dashboard.py
    └── register-power-package.py
```

Цей репозиторій містить конфігурацію для деплою, **не самі дані Home Assistant**. Для відновлення після перевстановлення Debian обов'язкова окрема резервна копія `/config`.
