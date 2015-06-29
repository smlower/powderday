#Code:  pd_front_end.py

#=========================================================
#IMPORT STATEMENTS
#=========================================================

import sys
script,pardir,parfile,modelfile = sys.argv
import numpy as np
import scipy.interpolate
import scipy.ndimage
import os.path
import copy
import pdb,ipdb

from hyperion.model import Model
import matplotlib as mpl
import matplotlib.pyplot as plt
from hyperion.model import ModelOutput
import h5py


import yt
from yt.units.yt_array import YTQuantity

sys.path.insert(0,pardir)
par = __import__(parfile)
model = __import__(modelfile)


import config as cfg
cfg.par = par #re-write cfg.par for all modules that read this in now
cfg.model = model

from astropy.table import Table
from astropy.io import ascii


from front_ends.front_end_controller import stream
from grid_construction import yt_octree_generate,grid_coordinate_boost,grid_center
import SED_gen as sg
from find_order import *
import powderday_test_octree as pto
import hyperion_octree_stats as hos
import error_handling as eh
import backwards_compatibility as bc


#=========================================================
#CHECK FOR THE EXISTENCE OF A FEW CRUCIAL FILES FIRST
#=========================================================

eh.file_exist(model.hydro_dir+model.Gadget_snap_name)
eh.file_exist(par.dustdir+par.dustfile)


#=========================================================
#Enforce Backwards Compatibility for Non-Critical Variables
#=========================================================
cfg.par.FORCE_RANDOM_SEED,cfg.par.BH_SED,cfg.par.IMAGING = bc.variable_set()

#=========================================================
#GRIDDING
#=========================================================


print 'Octree grid is being generated by yt'

fname = cfg.model.hydro_dir+cfg.model.Gadget_snap_name
field_add = stream(fname)

refined,dustdens,fc1,fw1,pf,ad = yt_octree_generate(fname,field_add)
xmin = (fc1[:,0]-fw1[:,0]/2.).convert_to_units('cm') #in proper cm 
xmax = (fc1[:,0]+fw1[:,0]/2.).convert_to_units('cm')
ymin = (fc1[:,1]-fw1[:,1]/2.).convert_to_units('cm')
ymax = (fc1[:,1]+fw1[:,1]/2.).convert_to_units('cm')
zmin = (fc1[:,2]-fw1[:,2]/2.).convert_to_units('cm')
zmax = (fc1[:,2]+fw1[:,2]/2.).convert_to_units('cm')


#dx,dy,dz are the edges of the parent grid
dx = (np.max(xmax)-np.min(xmin)).value
dy = (np.max(ymax)-np.min(ymin)).value
dz = (np.max(zmax)-np.min(zmin)).value


xcent = np.mean([np.min(xmin),np.max(xmax)]) #kpc
ycent = np.mean([np.min(ymin),np.max(ymax)])
zcent = np.mean([np.min(zmin),np.max(zmax)])

boost = np.array([xcent,ycent,zcent])
print '[pd_front end] boost = ',boost




#Tom Robitaille's conversion from z-first ordering (yt's default) to
#x-first ordering (the script should work both ways)


refined_array = np.array(refined)
refined_array = np.squeeze(refined_array)

order = find_order(refined_array)
refined_reordered = []
dustdens_reordered = np.zeros(len(order))



for i in range(len(order)): 
    refined_reordered.append(refined[order[i]])
    dustdens_reordered[i] = dustdens[order[i]]


refined = refined_reordered
dustdens=dustdens_reordered

#hyperion octree stats
max_level = hos.hyperion_octree_stats(refined)


pto.test_octree(refined,max_level)


np.save('refined.npy',refined)
np.save('density.npy',dustdens)






#========================================================================
#Initialize Hyperion Model
#========================================================================

m = Model()

if cfg.par.FORCE_RANDOM_SEED == True: m.set_seed(cfg.par.seed)

print 'Setting Octree Grid with Parameters: '



#m.set_octree_grid(xcent,ycent,zcent,
#                  dx,dy,dz,refined)
m.set_octree_grid(0,0,0,dx/2,dy/2,dz/2,refined)    


if par.PAH == True:
    frac = {'usg': 0.0586, 'vsg': 0.1351, 'big': 0.8063}
    for size in ['usg', 'vsg', 'big']:
        m.add_density_grid(dustdens * frac[size], par.dustdir+'%s.hdf5' % size)
        
    m.set_enforce_energy_range(cfg.par.enforce_energy_range)
else:
    m.add_density_grid(dustdens,par.dustdir+par.dustfile)



  


#generate dust model. This needs to preceed the generation of sources
#for hyperion since the wavelengths of the SEDs need to fit in the dust opacities.

df = h5py.File(par.dustdir+par.dustfile,'r')
o = df['optical_properties']
df_nu = o['nu']
df_chi = o['chi']

df.close()



#add sources to hyperion

stars_list,diskstars_list,bulgestars_list = sg.star_list_gen(boost,xcent,ycent,zcent,dx,dy,dz,pf,ad)
nstars = len(stars_list)




from source_creation import add_newstars,add_binned_seds,BH_source_add

if cfg.par.BH_SED == True: BH_source_add(m,pf,df_nu)


#figure out N_METAL_BINS:
fsps_metals = np.loadtxt(cfg.par.metallicity_legend)
N_METAL_BINS = len(fsps_metals)

if par.FORCE_BINNING == False:
    stellar_nu,stellar_fnu,disk_fnu,bulge_fnu = sg.allstars_sed_gen(stars_list,diskstars_list,bulgestars_list)
    m=add_newstars(df_nu,stellar_nu,stellar_fnu,disk_fnu,bulge_fnu,stars_list,diskstars_list,bulgestars_list,m)
    

#potentially write the stellar SEDs to a npz file
    if par.STELLAR_SED_WRITE == True:
        np.savez('stellar_seds.npz',par.COSMOFLAG,stellar_nu,stellar_fnu,disk_fnu,bulge_fnu)
        
else:
#note - the generation of the SEDs is called within
#add_binned_seds itself, unlike add_newstars, which requires
#that sg.allstars_sed_gen() be called first.
    
    m=add_binned_seds(df_nu,stars_list,diskstars_list,bulgestars_list,m)




nstars = len(stars_list)
nstars_disk = len(diskstars_list)
nstars_bulge = len(bulgestars_list)


   

    

if par.SOURCES_IN_CENTER == True:
    for i in range(nstars):
        stars_list[i].positions[:] = 0
        bulgestars_list[i].positions[:] = 0
        diskstars_list[i].positions[:] = 0 






print 'Done adding Sources'

print 'Setting up Model'
m_imaging = copy.deepcopy(m)


#set up the SEDs and images
m.set_raytracing(True)
m.set_n_photons(initial=par.n_photons_initial,imaging=par.n_photons_imaging,
                raytracing_sources=par.n_photons_raytracing_sources,raytracing_dust=par.n_photons_raytracing_dust)
m.set_n_initial_iterations(7)
m.set_convergence(True,percentile=99.,absolute=1.01,relative=1.01)


sed = m.add_peeled_images(sed = True,image=False)
sed.set_wavelength_range(250,0.001,1000.)
sed.set_viewing_angles(np.linspace(0,90,par.NTHETA).tolist()*par.NPHI,np.repeat(np.linspace(0,90,par.NPHI),par.NPHI))
sed.set_track_origin('basic')

print 'Beginning RT Stage'
#Run the Model
m.write(model.inputfile+'.sed',overwrite=True)
m.run(model.outputfile+'.sed',mpi=True,n_processes=par.n_processes,overwrite=True)



#see if the variable exists to make code backwards compatible

if cfg.par.IMAGING == True:
    #read in the filters file
    filters = np.loadtxt(par.filter_file)
    print "Beginning Monochromatic Imaging RT"


    m_imaging.set_raytracing(True)
    m_imaging.set_monochromatic(True,wavelengths=filters)
    
    m_imaging.set_n_photons(initial = par.n_photons_initial,
                            imaging_sources = par.n_photons_imaging,
                            imaging_dust =  par.n_photons_imaging,
                            raytracing_sources=par.n_photons_raytracing_sources,
                            raytracing_dust = par.n_photons_raytracing_dust)
    m_imaging.set_n_initial_iterations(7)
    m_imaging.set_convergence(True,percentile=99.,absolute=1.01,relative=1.01)
    image = m_imaging.add_peeled_images(sed = True, image = True)
    image.set_viewing_angles(np.linspace(0,90,par.NTHETA).tolist()*par.NPHI,np.repeat(np.linspace(0,90,par.NPHI),par.NPHI))
    image.set_track_origin('basic')
    image.set_image_size(cfg.par.npix_x,cfg.par.npix_y)
    image.set_image_limits(-dx,dx,-dy,dy)
    
    m_imaging.write(model.inputfile+'.image',overwrite=True)
    m_imaging.run(model.outputfile+'.image',mpi=True,n_processes=par.n_processes,overwrite=True)
   












