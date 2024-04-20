from mall import  app
import logging

LOG = logging.getLogger(__name__)

def main():
    LOG.info(app.url_map)
    app.run(host="0.0.0.0", port=8099, threaded=True)


if __name__ == "__main__":
    main()