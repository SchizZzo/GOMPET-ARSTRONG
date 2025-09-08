# GOMPET_2


make all - aby uruchmic wszystko co potrzebnne przy pierwszym uruchomieniu.

all:
	$(MAKE) makemigrations
	$(MAKE) migrate
	$(MAKE) collectstatic
	$(MAKE) populatedb
	$(MAKE) createsuperuser
	$(MAKE) run

po uruchomieniu wszyskiekgo bedzie wstepnie wypelniona baza jesli utworzyc superuser to bedziesz miec uzytkownika do testow.


dokładny adres dla api:
http://localhost/api/v2/redoc/

np. bierzesz adres 
http://localhost/api/v2/users/users/

to musisz z endpointa usunac /api/v2 aby działalo poprawnie.

POST
http://localhost/users/users/

