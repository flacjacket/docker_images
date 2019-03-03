FROM quantumobject/docker-zoneminder

RUN  a2enmod ssl \
  && sed -i -e 's:/etc/ssl/certs/ssl-cert-snakeoil.pem:/etc/letsencrypt_certs/fullchain.pem:' /etc/apache2/sites-available/default-ssl.conf \
  && sed -i -e 's:/etc/ssl/private/ssl-cert-snakeoil.key:/etc/letsencrypt_certs/privkey.pem:' /etc/apache2/sites-available/default-ssl.conf \
  && ln -s ../sites-available/default-ssl.conf /etc/apache2/sites-enabled/
