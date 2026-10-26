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

## Оновлення

Версії сторонніх інтеграцій закріплено commit SHA у `Dockerfile`. Для оновлення зміни відповідні `ARG`, перевір релізи та зроби новий деплой. Перезапуск контейнера також синхронізує код інтеграцій з образу, тож **не оновлюй ці дві інтеграції через HACS** — наступний запуск перезапише їх код.

Тег базового Home Assistant за замовчуванням — `stable`, він може змінюватися з часом. Якщо потрібна повна повторюваність, зафіксуй конкретний версійний тег або digest базового образу.

## Структура

```text
.
├── Dockerfile
├── compose.yaml
├── .env.example
├── .dockerignore
└── scripts/
    └── sync-integrations.sh
```

Цей репозиторій містить конфігурацію для деплою, **не самі дані Home Assistant**. Для відновлення після перевстановлення Debian обов'язкова окрема резервна копія `/config`.
