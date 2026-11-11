# Build stage
FROM node:20-alpine AS build
WORKDIR /app
# Install exactly the versions in package-lock.json (repeatable builds)
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
# Apply the latest Alpine security fixes (the base image can lag behind)
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
