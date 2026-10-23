FROM alpine:3.20

# ffmpeg ghép video, rsvg-convert đổi SVG sang PNG, font-dejavu có chữ tiếng Việt
RUN apk add --no-cache ffmpeg python3 rsvg-convert font-dejavu

WORKDIR /app
COPY server.py .

EXPOSE 8000
CMD ["python3", "-u", "server.py"]
