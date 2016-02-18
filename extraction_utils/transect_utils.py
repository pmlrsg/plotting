import csv
import datetime

def get_transect_bounds(_csv):
	print _csv
	with open(_csv, "rb") as csvfile:
		data = csv.DictReader(csvfile, delimiter=',')
		lats = []
		lons = []
		for row in data:
			lats.append(float(row['Lat']))
			lons.append(float(row['Lon']))
	return (min(lons), min(lats), max(lons), max(lats))


def get_transect_times(_csv):
	with open(_csv, "rb") as csvfile:
		data = csv.DictReader(csvfile, delimiter=',')
		dates = []
		for row in data:
			date = row['Dates'].split(' ')[0]
			dates.append(datetime.datetime.strptime(date, '%d/%m/%Y'))
	return "%s/%s" % (min(dates), max(dates))