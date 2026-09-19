# Dockerfile for CO2Ops AWS Sustainability Frontend Console
FROM nginx:alpine

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static assets (HTML, JS, CSS, images)
COPY . /usr/share/nginx/html/

# Expose standard HTTP port
EXPOSE 80

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]