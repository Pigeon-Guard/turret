# Pigeon Guard - Turret

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the project root:

```shell
cp .env.example .env
```

Then edit `.env` with your settings. See `.env.example` for all available options.

## Usage

## Raspberry Pi Zero 2 W

**Prerequisites:**

- [Install Docker on your Raspberry Pi Zero 2 W](https://docs.docker.com/engine/install/debian/)

**Installation:**

```shell
mkdir ~/turret
cd ~/turret

wget https://github.com/Pigeon-Guard/turret/raw/refs/heads/main/.env.example -O .env
wget https://github.com/pigeon-guard/turret/raw/refs/heads/main/compose-pi.yml -O compose.yml
```

**Start:**

```shell
cd ~/turret
docker compose up -d
```

**Stop:**

```shell
cd ~/turret
docker compose down
```

**Debugging:**

```shell
cd ~/turret
docker compose logs -f
```
