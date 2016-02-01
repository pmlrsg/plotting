import urllib
import urllib2
import tempfile
import numpy as np
import netCDF4 as netCDF
from shapely import wkt
from PIL import Image, ImageDraw

def create_mask(poly, params, poly_type="polygon"):
   '''
   takes a Well Known Text polygon or line 
   and produces a masking array for use with numpy
   @param poly - WKT polygon or line
   @param variable - WCS variable to mask off
   @param type - one from [polygon, line]
   '''
   loaded_poly = wkt.loads(poly)
   wcs_envelope = loaded_poly.envelope
   bounds =  wcs_envelope.bounds
   bb = ','.join(map(str,bounds))
   params['bbox']._value = bb
   params['url'] = createURL(params)
   variable = params['coverage'].value
   #wcs_url = wcs_base_url % (bounds[0],bounds[1],bounds[2],bounds[3])
   wcs_url = params['url'].value
   #testfile=urllib.URLopener()
   #testfile.retrieve(wcs_url,"%s.nc" % variable)
   try:
      resp = contactWCSServer(wcs_url)
   except urllib2.HTTPError:
      params["vertical"]._value = params["vertical"].value[1:]
      params['url'] = createURL(params)
      wcs_url = params['url'].value
      resp = contactWCSServer(wcs_url)
   tfile = saveOutTempFile(resp)
   to_be_masked = netCDF.Dataset(tfile, 'r+')

   chl = to_be_masked.variables[variable][:]

   latvals = to_be_masked.variables[str(getCoordinateVariable(to_be_masked, 'Lat').dimensions[0])][:]
   lonvals = to_be_masked.variables[str(getCoordinateVariable(to_be_masked, 'Lon').dimensions[0])][:]

   from shapely.geometry import Polygon
   minlat = min(latvals)
   maxlat = max(latvals)
   minlon = min(lonvals)
   maxlon = max(lonvals)

   lonlat_poly = Polygon([[minlon,maxlat],[maxlon,maxlat],[maxlon,minlat],[minlon,minlat],[minlon,maxlat]])
   #print '#'*50
   #print lonlat_poly
   lonlat_poly = lonlat_poly.buffer(0)
   overlap_poly = loaded_poly.intersection(lonlat_poly)
   poly = poly[trim_sizes[poly_type]]

   poly = poly.split(',')
   poly = [x.split() for x in poly]



   #found_lats = [find_closest(latvals, float(x[1])) for x in poly]
   #found_lons = [find_closest(lonvals, float(x[0])) for x in poly]
   if overlap_poly.type == "MultiPolygon":
      found = []
      for poly in overlap_poly:
         found_lats = [find_closest(latvals, float(x)) for x in poly.exterior.xy[1]]
         found_lons = [find_closest(lonvals, float(x)) for x in poly.exterior.xy[0]]
         found.append(zip(found_lons,found_lats))


   elif overlap_poly.type == "MultiLineString":
      found = []
      for poly in overlap_poly:
         found_lats = [find_closest(latvals, float(x)) for x in poly.xy[1]]
         found_lons = [find_closest(lonvals, float(x)) for x in poly.xy[0]]
         found.append(zip(found_lons,found_lats))

   else:
      if poly_type is 'line':
         found_lats = [find_closest(latvals, float(x)) for x in overlap_poly.xy[1]]
         found_lons = [find_closest(lonvals, float(x)) for x in overlap_poly.xy[0]]
      else:
         found_lats = [find_closest(latvals, float(x)) for x in overlap_poly.exterior.xy[1]]
         found_lons = [find_closest(lonvals, float(x)) for x in overlap_poly.exterior.xy[0]]

      #found = zip(overlap_poly.exterior.xy[0],overlap_poly.exterior.xy[1])
      found = zip(found_lons,found_lats)

   # img = Image.new('L', (chl.shape[2],chl.shape[1]), 0)
   img = Image.new('L', (chl.shape[to_be_masked.variables[variable].dimensions.index(str(getCoordinateVariable(to_be_masked, 'Lon').dimensions[0]))],chl.shape[to_be_masked.variables[variable].dimensions.index(str(getCoordinateVariable(to_be_masked, 'Lat').dimensions[0]))]), 0)

   if overlap_poly.type == "MultiPolygon":
      for f in found:
         ImageDraw.Draw(img).polygon(f,  outline=2, fill=2)
   elif overlap_poly.type == "MultiLineString":
      for f in found:
         ImageDraw.Draw(img).polygon(f,  outline=2, fill=2)
   else:
      if poly_type == 'polygon':
         ImageDraw.Draw(img).polygon(found,  outline=2, fill=2)
      if poly_type == 'line':
         ImageDraw.Draw(img).line(found,   fill=2)

   masker = np.array(img)
   #fig = plt.figure()
   masked_variable = []
   for i in range(chl.shape[0]):
      #print i
      masked_variable.append(np.ma.masked_array(chl[i,:], mask=[x != 2 for x in masker]))
      masked_variable[i].filled(-999)
   #    a = fig.add_subplot(1,5,i+1)
   #    imgplot = plt.imshow(masked_variable)

   # plt.show()

   return masked_variable, to_be_masked, masker, tfile, variable


"""
Performs a basic set of statistical functions on the provided data.
"""
def basic(dataset, variable, irregular=False, original=None):
   import matplotlib
   matplotlib.use('Agg')
   import matplotlib.pyplot as plt   
   if irregular:
      # current_app.logger.debug('irregular shape')
      # current_app.logger.debug([x.shape for x in dataset])

      #arr = np.ma.concatenate(dataset)
      arr = np.ma.array(dataset)

      #_img = Image.fromarray(arr[0], 'RGB')
      #_img.save('/users/rsg/olcl/irregular_test/my.png')
      # plt.imshow(arr[0])
      # plt.savefig('/users/rsg/olcl/irregular_test/my.png')
      # current_app.logger.debug('irregular shape after concatonate')
      # current_app.logger.debug(arr)
   else:
      arr = np.array(dataset.variables[variable])
   #current_app.logger.debug(arr)
   # Create a masked array ignoring nan's
   if original is not None:
      dataset = original
   if not irregular:
      maskedArray = np.ma.masked_invalid(arr)
   else:
      maskedArray = np.ma.masked_invalid(arr)
   #maskedArray = arr
   plt.imshow(maskedArray[0])
   plt.savefig('/users/rsg/olcl/irregular_test/my_masked.png')
   time = getCoordinateVariable(dataset, 'Time')
   # current_app.logger.debug('time channel test')
   # current_app.logger.debug(time)
   if time == None:
      g.graphError = "could not find time dimension"
      return
   
   times = np.array(time)
   output = {}
   
   units = getUnits(dataset.variables[variable])
   output['units'] = units
   
   
   #mean = getMean(maskedArray)
   #median = getMedian(maskedArray)
   #std = getStd(maskedArray)
   #min = getMin(maskedArray)
   #max = getMax(maskedArray)
   timeUnits = getUnits(time)
   start = None
   if timeUnits:
      start = (netCDF.num2date(times[0], time.units, calendar='standard')).isoformat()
   else: 
      start = ''.join(times[0])
   
   #=========================================================================
   # if np.isnan(max) or np.isnan(min) or np.isnan(std) or np.isnan(mean) or np.isnan(median):
   #   output = {}
   #   g.graphError = "no valid data available to use"
   # else:
   #   output['global'] = {'mean': mean, 'median': median,'std': std, 'min': min, 'max': max, 'time': start}
   #=========================================================================
   
   output['global'] = {'time': start}
   
   output['data'] = {}
   
   for i, row in enumerate(maskedArray):
      if timeUnits:
         date = netCDF.num2date(time[i], time.units, calendar='standard').isoformat()
      else:     
         date = ''.join(times[i])
      mean = getMean(row)
      median = getMedian(row)
      std = getStd(row)
      min = getMin(row)
      max = getMax(row)
      
      if np.isnan(max) or np.isnan(min) or np.isnan(std) or np.isnan(mean) or np.isnan(median):
         pass
      else:
         output['data'][date] = {'mean': mean, 'median': median,'std': std, 'min': min, 'max': max}
   
   if len(output['data']) < 1:
      g.graphError = "no valid data available to use"
      return output
      
   
   return output



def hovmoller(dataset, params):
   xAxisVar = params['graphXAxis'].value
   yAxisVar = params['graphYAxis'].value
   zAxisVar = params['graphZAxis'].value

   xVar = getCoordinateVariable(dataset, xAxisVar)
   xArr = np.array(xVar)
   yVar = getCoordinateVariable(dataset, yAxisVar)
   yArr = np.array(yVar)
   zArr = np.array(dataset.variables[zAxisVar])
   
   if xVar == None:
      g.graphError = "could not find %s dimension" % xAxisVar
      return
   if yVar == None:
      g.graphError = "could not find %s dimension" % yAxisVar
      return
   
   # Create a masked array ignoring nan's
   zMaskedArray = np.ma.masked_invalid(zArr)
      
   time = None
   lat = None
   lon = None
   
   if xAxisVar == 'Time':
      times = xArr
      time = xVar
      lat = yArr
   else:        
      lon = xArr
      times = yArr
      time = yVar

   output = {}
   
   timeUnits = getUnits(time)
   start = None
   if timeUnits:
      start = (netCDF.num2date(times[0], time.units, calendar='standard')).isoformat()
   else: 
      start = ''.join(times[0])
   
   output['global'] = {'time': start}
   
   output['data'] = []
 
   numDimensions = len(zMaskedArray.shape)
   
   direction = None 
   if lat != None:
      direction = 'lat'
   elif lon != None:
      direction = 'lon'
      if numDimensions == 4:
         zMaskedArray = zMaskedArray.swapaxes(2,3)
      else:
         zMaskedArray = zMaskedArray.swapaxes(1,2) # Make it use Lon instead of Lat
   

   # If 4 dimensions, assume depth and switch with time
   if numDimensions == 4:
      depth = np.array(getDepth(dataset))
      if len(depth.shape) > 1:
         print 'WARNING: There are multiple depths.'
      else:
         # Presume 1 depth, set to contents of depth
         # This way, it will enumerate over correct array
         # whether depth or not
         zMaskedArray = zMaskedArray.swapaxes(0,1)[0]
         
         output['depth'] = float(depth[0])
 

   for i, timelatlon in enumerate(zMaskedArray):
      date = None    
      if timeUnits:
         date = netCDF.num2date(time[i], time.units, calendar='standard').isoformat()
      else:     
         date = ''.join(times[i])
      
      for j, row in enumerate(timelatlon):
         
         if direction == "lat":
            pos = lat[j]
         elif direction == "lon":
            pos = lon[j]
         
         mean = getMean(row)
         
         if not np.isnan(mean):
            output['data'].append([date, float(pos), mean])
            
   if len(output['data']) < 1:
      g.graphError = "no valid data available to use"
      error_handler.setError('2-07', None, g.user.id, "views/wcs.py:hovmoller - No valid data available to use.")
      return output
      
   
   return output


def getHistogram(arr):
   maskedarr = np.ma.masked_array(arr, [np.isnan(x) for x in arr])
   bins = request.args.get('bins', None) # TODO move to get params
   numbers = []
   current_app.logger.debug('before bins') # DEBUG
   
   if bins == None or not bins:
      max = getMax(maskedarr)
      min = getMin(maskedarr)
      bins = np.linspace(min, max, 11) # Create ten evenly spaced bins 
      current_app.logger.debug('bins generated') # DEBUG
      N,bins = np.histogram(maskedarr, bins) # Create the histogram
   else:
      values = bins.split(',')
      for i,v in enumerate(values):
         values[i] = float(values[i]) # Cast string to float
      bins = np.array(values)
      current_app.logger.debug('bins converted') # DEBUG
      N,bins = np.histogram(maskedarr, bins) # Create the histogram
   
   current_app.logger.debug('histogram created') # DEBUG
   for i in range(len(bins)-1): # Iter over the bins       
      if np.isnan(bins[i]) or np.isnan(bins[i+1] or np.isnan(N[i])):
         g.graphError = 'no valid data available to use'
         return       
      
      numbers.append((bins[i] + (bins[i+1] - bins[i])/2, float(N[i]))) # Get a number halfway between this bin and the next
   return {'Numbers': numbers, 'Bins': bins.tolist()}


"""
Utility function to find the time dimension from a netcdf file. Needed as the
time dimension will not always have the same name or the same attributes.
"""
def getCoordinateVariable(dataset, axis):
   for i, key in enumerate(dataset.variables):
      var = dataset.variables[key]
      #current_app.logger.debug("========== key:" + key + " ===========") # DEBUG
      for name in var.ncattrs():
         #current_app.logger.debug(name) # DEBUG
         if name == "_CoordinateAxisType" and var._CoordinateAxisType == axis:
            return var
   
   return None

def getDepth(dataset):
   for i, key in enumerate(dataset.variables):
      var = dataset.variables[key]
      if "_CoordinateAxisType" in var.ncattrs() and "_CoordinateZisPositive" in var.ncattrs():
         #if var._CoordinateAxisType == "Height" and var._CoordinateZisPositive == "down":
         if var._CoordinateAxisType == "Height":
            return var
   return None

def getDimension(dataset, dimName):
   for i, key in enumerate(dataset.dimensions):
      current_app.logger.debug(key)
      dimension = dataset.dimensions[key]
      if key == dimName:
         return len(dimension)
   
   return None

def getUnits(variable):
   for name in variable.ncattrs():
      if name == "units":
         return variable.units
      
   return ''


"""
Returns the median value from the provided array.
"""
def getMedian(arr):
   return float(np.ma.median(arr))

"""
Returns the mean value from the provided array.
"""
def getMean(arr):
   return float(np.mean(arr))

"""
Returns the std value from the provided array.
"""
def getStd(arr):
   return float(np.std(arr.compressed()))

"""
Returns the minimum value from the provided array. 
"""
def getMin(arr):
   return float(np.min(arr)) # Get the min ignoring nan's, then cast to float

"""
Returns the maximum value from the provided array.
"""
def getMax(arr):
   return float(np.max(arr)) # Get the max ignoring nan's, then cast to float
