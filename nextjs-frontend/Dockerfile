FROM node:20-bookworm

WORKDIR /app

RUN npm install -g pnpm

# Install deps as root first (volume will overlay /app later in dev)
COPY package*.json ./
RUN pnpm install

USER node

COPY . .

EXPOSE 3000

CMD ["bash", "start.sh"]
