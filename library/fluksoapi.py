# -*- coding: utf-8 -*-
"""
Created on Mon Jan 21 15:31:36 2013 by Carlos Dierckxsens

"""
import datetime as dt
import pandas as pd
import requests
import os
from time import mktime,strftime
import pdb
import inspect
import requests
import re
import zipfile
import glob

def pull_api(sensor, token, unit, interval='day', resolution = 'minute'):
   
    """     
   
    Function for downloading data from fluksometers
    
    Parameters
    ----------
    - inverval: string specifying the interval (day, month, ...)
    - sensor :  sensor name (from the flukso.net sensor tab)
    - token :  sensor token (from the flukso.net sensor tab)
    - resolution: time resolution (e.g. minute, 15min, hour, day, week, month, 
      year, decade, night)
    - unit: unit of measurements (e.g. watt, kwhperyear, lperday)

    Note
    ----
    The Flukso Server will automatically restrict the data to what's available
    
    
    Returns
    -------
    Resulf of the http request with the raw data.  
    Use the save2csv function to parse and save.
    
    """
    
    payload = {'interval'   :   interval,
               'resolution' :   resolution,
               'unit'       :   unit}
               
    headers = {'Accept'     :   'application/json', 
               'X-Version'  :   '1.0', 
               'X-Token'    :   token}  
               
    url = 'https://api.flukso.net' + '/sensor/' + sensor 
    
    # Send Request
    try:    
        s = requests.Session()
        r = s.get(url, params = payload, headers = headers, verify=False)
    except:
        print "-------> Problem with HTTP request to Flukso <-------"
    
    # check result
    
    if not r.ok:
        print "The flukso api GET request did not succeed."
        print "Some details:"
        print "Request headers:"
        print r.request.headers
        print "Request url:"
        print r.request.url
        
        
    
    return r


def parse(r):
    """
    Parse and return a pandas TimeSeries object
    """
    
    
    # Create TimeSeries   
    try:
        d = {}
        for tup in r.json():
            d[dt.datetime.fromtimestamp(tup[0])] = tup[1]
        
    except:
        print "-------> Problem with Flukso data parsing <-------"
        raise
    
    #pdb.set_trace()
    Ts = pd.TimeSeries(data=d)
    # Convert the index to a pandas DateTimeIndex 
    Ts.index = pd.to_datetime(Ts.index)
    # this line gives an error.  Should be checked, but for now I keep the nan's        
    # Ts = Ts[Ts != 'nan']
    
    return Ts


def save_csv(Ts, csvpath=None, fileNamePrefix=''):
    """
    Save the TimeSeries or DataFrame to csv with specified name
    """
    
   
    # save to file
    if csvpath is None:
        csvpath = os.getcwd()
    s = Ts.index[0].strftime(format="%Y-%m-%d_%H-%M-%S")
    e = Ts.index[-1].strftime(format="%Y-%m-%d_%H-%M-%S")
        
    csv = os.path.join(csvpath, fileNamePrefix + '_FROM_' + s + 
                                    '_TO_' + e + '.csv')
    
    Ts.to_csv(csv, header=False)
    return csv    

   
def find_csv(folder, sensor):
    """
    Find csv file corresponding to sensor in the given folder.  Run consolidate
    first if there are multiple csv files for a given sensor.
    
    Parameters
    ----------
    
    folder : path
        Folder containing the csv files
    sensor : hex
        Sensor for which files are to be consolidated
        
    Returns
    -------
    
    path : absolute pathname to found csv
    
    Raises
    ------
    
    ValueError when more than one file is found
    """
    
    files = os.listdir(folder)
    found = filter(lambda x: x.find(sensor) > -1, files)

    if len(found) > 1:
        return []
        raise ValueError("More than one csv-file found for sensor {}.\nRun fluksoapi.consolidate() first".format(sensor))
    elif len(found) ==0:
        return []
        raise ValueError("No file found for this sensor {} ".format(sensor))		
    else:
        return os.path.join(folder, found[0])
    
    

def load_csv(csv):
    """
    Load a previously saved csv file into a dataframe and return it.
    
    Parameters
    ----------
    csv : path
        Path to a csv file.  Filename should be something like fluksoID_sensor_FROM_x_to_y.csv

    Returns
    -------
    df : pandas.DataFrame
        The dataframe will have a DatetimeIndex with UTC timezone.  The 
        column will be the sensor-ID, extracted from the csv filename. If invalid filename is given, an empty dataframe will be returned.
    
    """
    empty = pd.DataFrame()
    if len(csv) == 0:
        return empty
        raise ValueError("Please give valid file name as input")
    elif  csv.find('FROM')==False:
        return empty
        raise ValueError("unable to load file {}. Please give data file as input. Its typically named FL***_sensorID_FROM_DD-MM-YYYY_TO_DD-MM-YYYY.csv".format(csv))
    else:
        df = pd.read_csv(csv, index_col = 0, header=None, parse_dates=True)
        # Convert the index to a pandas DateTimeIndex 
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize('UTC')
        df.columns = [csv.split('_')[-7]]
        return df


def consolidate_sensor(folder, sensor, dt_day=None, remove_temp=False):
    """
    Merge all csv files for a given sensor into a single csv file
    
    - the given sensor
    - and the given day
    into a single csv file
    
    Parameters
    ----------
    folder : path
        Folder containing the csv files
    sensor : hex
        Sensor for which files are to be consolidated
    dt_day : (optional) datetime
        If a valid datetime is passed, only files containing data from this day 
        will be considered
    remove_temp : (optional) Boolean, default=False
        If True, only the resulting consolidated csv is kept, the files that
        have been consolidated are deleted.
    """
    if dt_day is not None:    
        dt_day_string = dt_day.strftime(format="%Y-%m-%d")     
    
    # List all files for the given sensor in the given path & withouth hidden ones:			
	# glob.glob checks for hidden files 'start with '.' and then does os.listdir(folder).
    files = [f for f in glob.glob(os.path.join(folder, '*')) if (f.find(sensor) > -1)]
		
    if dt_day is not None:
        files = [f for f in files if f.find(dt_day_string) > -1]

    if files == []:
        print 'No (unhidden) files found for sensor '+sensor+' in '+folder 
        # Changed from valueerror to print, since else valueerror is raised if hidden files present.
    if (len(files) > 1 ): # If multiple (unhidden) files for one sensor are present, then consolidate
        print("About to consolidate {} files for sensor {}".format(len(files), sensor))
        timeseries = [load_csv(os.path.join(folder, f)) for f in files]
        combination = timeseries[0]    
        for ts in timeseries[1:]:
            combination = combination.combine_first(ts)
    
        if dt_day is not None:
            # only retain data from this day
            dt_start = dt.datetime.strptime(dt_day_string, "%Y-%m-%d")
            dt_end = dt_start + dt.timedelta(days=1)
            combination = combination.ix[dt_start:dt_end]
        if remove_temp:    
            for f in files:
                os.remove(os.path.join(folder, f))
            print("Removed the {} temporary files".format(len(files)))
        # Obtain the new filename prefix, something like FX12345678_sensorid_
        # the _FROM....csv will be added by the save_csv method
        prefix_end = files[-1].index('_FROM')
        prefix = files[-1][:prefix_end]    
        csv = save_csv(combination, csvpath = folder, fileNamePrefix=prefix)
        print('Saved ', csv)
        return csv
		
    else: # If just one file to consolidate, then give message and stop
        print("No files consolidated for {} (only 1 present).".format(sensor))
    


    


def consolidate_folder(folder):
    
    sensorlist = [x.split('_')[1] for x in os.listdir(folder)]
    sensors = set(sensorlist)
    
    for s in sensors:
        consolidate_sensor(folder, s, remove_temp=True) 
        

def synchronize(folder, unzip=True, consolidate=True):
    """Download the latest zip-files from the opengrid droplet, unzip and consolidate.
    
    The files will be stored in folder/zip and unzipped and 
    consolidated into folder/csv
    
    Parameters
    ----------
    
    folder : path
        The *data* folder, containing subfolders *zip* and *csv*
    unzip : [True]/False
        If True, unzip the downloaded files to folder/csv
    consolidate : [True]/False
        If True, all csv files in folder/csv will be consolidated to a 
        single file per sensor
    
    Notes
    -----
    
    This will only unzip the downloaded files and then consolidate all
    csv files in the csv folder.  If you want to rebuild the consolidated
    csv from all available data you can either delete all zip files and 
    run this function or run _unzip(folder, consolidate=True) on the 
    data folder.
        
    """
    
    if not os.path.exists(folder):
        raise IOError("Provide your path to the data folder where a zip and csv subfolder will be created.")
    from opengrid.library import config
    # Get the pwd; start from the path of this current file 
    sourcedir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    c = config.Config()
    pwd = c.get('opengrid_server', 'password')
    host = c.get('opengrid_server','host')
    port = c.get('opengrid_server','port')
    user = c.get('opengrid_server','user')
    URL = "".join(['http://',host,':',port,'/'])
    
    # create a session to the private opengrid webserver
    session = requests.Session()
    session.auth = (user, pwd)
    resp = session.get(URL)
    
    # make a list of all zipfiles
    pattern = '("[0-9]{8}.zip")' 
    zipfiles = re.findall(pattern, resp.content)
    zipfiles = [x.strip('"') for x in zipfiles]
    zipfiles.append('all_data_till_20140711.zip')
    
    zipfolder = os.path.join(folder, 'zip')    
    csvfolder = os.path.join(folder, 'csv')

    # create the folders if they don't exist
    for fldr in [zipfolder, csvfolder]:
        if not os.path.exists(fldr):
            os.mkdir(fldr)
    
    downloadfiles = [] # these are the successfully downloaded files       
    for f in zipfiles:
        # download the file to zipfolder if it does not yet exist
        if not os.path.exists(os.path.join(zipfolder, f)):
            print("Downloading {}".format(f))       
            with open(os.path.join(zipfolder, f), 'wb') as handle:
                response = session.get('http://95.85.34.168:8080/' + f, stream=True)
        
                if not response.ok:
                    raise IOError('Something went wrong in downloading of {}'.format(f))
        
                for block in response.iter_content(1024):
                    if not block:
                        break
                    handle.write(block)
            downloadfiles.append(f)
            
    # Now unzip and consolidate the downloaded files only
    if unzip:
        _unzip(folder=folder, files=downloadfiles, consolidate=consolidate)
        

def _unzip(folder, files='all', consolidate=True):
    """
    Unzip zip files from folder/zip to folder/csv and consolidate if wanted
        
    Parameters
    ----------
    
    folder : path
        The *data* folder, containing subfolders *zip* and *csv*
    files = 'all' (default) or list of files
        Unzip only these files
    consolidate : [True]/False
        If True, all csv files in folder/csv will be consolidated to a 
        single file per sensor
    
    """

    zipfolder = os.path.join(folder, 'zip')    
    csvfolder = os.path.join(folder, 'csv')

    # create the folders if they don't exist
    for fldr in [zipfolder, csvfolder]:
        if not os.path.exists(fldr):
            os.mkdir(fldr)

    if files == 'all':
        files = os.listdir(zipfolder)
    badfiles = []
    
    for f in files:
        # now unzip to zipfolder
        try:       
            z = zipfile.ZipFile(os.path.join(zipfolder, f), 'r')
            z.extractall(path=csvfolder)
        except:
            badfiles.append(f)
            pass
    
    if badfiles:
        print("Could not unzip these files:")
        for f in badfiles:
            print f
        
    if consolidate:
        # create a set of unique sensor id's in the csv folder        
        consolidate_folder(csvfolder)            
  
    

 
    
