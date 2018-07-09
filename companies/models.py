from django.db import models

ABSCHLUSS_CHOICES = ['Jahresabschluss', 'Konzernabschluss']


class Company(models.Model):
    name = models.CharField(max_length=128)
    gericht = models.CharField()
    FN = models.CharField(max_length=8)
    street = models.CharField()
    postal_code = models.IntegerField()
    city = models.CharField()
    compass_id = models.IntegerField()
    dvr_number = models.IntegerField()
    first_entry = models.DateField()
    exporting_countries = models.CharField()
    founding_year = models.IntegerField()
    importing_countries = models.CharField()
    languages = models.CharField()
    last_entry = models.DateField()
    brand_name = models.CharField()
    oenb_number = models.CharField()
    headquarter = models.CharField()
    industries = models.CharField()
    telephone = ''
    UID = ''
    deleted = ''


class Administrative(models.Model):
    FN = models.ForeignKey(Company, on_delete=models.CASCADE)
    Anteil_rel = models.FloatField()
    birthdate = models.DateField()


class Abschluss(models.Model):
    FN = models.ForeignKey(Company, on_delete=True)
    comment = models.CharField()
    description = models.CharField()
    type = models.CharField(choices=ABSCHLUSS_CHOICES)


class Balance(models.Model):
    FN = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    parents = models.CharField(max_length=128)
    value = models.FloatField()


class BalanceInfo(models.Model):
    FN = models.ForeignKey(Company, on_delete=models.CASCADE)
    year = models.IntegerField()
    shortened = models.BooleanField()
