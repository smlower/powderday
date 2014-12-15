
import numpy as np
import pdb,ipdb
from yt.mods import *
from yt.fields.particle_fields import add_volume_weighted_smoothed_field
import sys
import config as cfg
import constants as const

from cutout_data import yt_field_map
from yt.frontends.sph.data_structures import ParticleDataset
from front_ends.gadget2pd import *

ParticleDataset.filter_bbox = True
ParticleDataset._skip_cache = True



def octree_zoom(fname,pf,unit_base,bbox):

    pf = load(fname,unit_base=unit_base,bounding_box=bbox,over_refine_factor=cfg.par.oref,n_ref=cfg.par.n_ref)

    pf.index
    ad = pf.all_data()

    print '\n\n'
    print '----------------------------'
    print '[octree zoom] Entering Octree Zoom with parameters: '
    print "[octree zoom] (...Calculating Center of Mass in octree_zoom)"
    #    com = ad.quantities.center_of_mass()

    
    gas_com_x = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,0])/np.sum(ad["gasdensity"])
    gas_com_y = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,1])/np.sum(ad["gasdensity"])
    gas_com_z = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,2])/np.sum(ad["gasdensity"])
    
    com = [gas_com_x,gas_com_y,gas_com_z]

    print "[octree zoom] Center of Mass is at coordinates (kpc): ",com




    minbox = np.array(com)-cfg.par.zoom_box_len
    maxbox = np.array(com)+cfg.par.zoom_box_len


    region = pf.region(com,minbox,maxbox)


    print '[octree zoom] minimum edges of the zoomed box are: (kpc)',minbox
    print '[octree zoom] maximum edges of the zoomed box are: (kpc)',maxbox
    print '----------------------------'
    print '\n'

    
    

    data,skip = yt_field_map(region)


                     
    #because minbox can be negative or positive (as can maxbox), and
    #we want to make sure we go *just* beyond those values for bbox to
    #encapsulate all of the particles in region, we have to have some
    #np.min and max arguments in the bbox definition.

    bbox = [[np.min([minbox[0]*1.0001,minbox[0]*0.9999]), 
             np.max([maxbox[0]*1.0001,maxbox[0]*0.9999])],
            [np.min([minbox[1]*1.0001,minbox[1]*0.9999]),
             np.max([maxbox[1]*1.0001,maxbox[1]*0.9999])],
            [np.min([minbox[2]*1.0001,minbox[2]*0.9999]),
             np.max([maxbox[2]*1.0001,maxbox[2]*0.9999])]]



    new_ds = load_particles(data,
                            length_unit = unit_base['UnitLength_in_cm'],
                            mass_unit = unit_base['UnitMass_in_g'],
                            velocity_unit = unit_base['UnitVelocity_in_cm_per_s'],
                            bbox=np.array(bbox),
                            n_ref = cfg.par.n_ref,over_refine_factor=cfg.par.oref)
    
    
    new_ds.particle_types_raw = tuple(pt for pt in pf.particle_types_raw 
                                      if pt not in skip)
    new_ds.index

    #make sure that the metallicity particles make the translation
    new_ds.field_info["PartType0","metallicity"].particle_type=True

    new_ad = new_ds.all_data()
    

        
    return new_ds


def octree_zoom_bbox_filter(fname,pf,unit_base,bbox0):

    ds0 = pf
    
    ds0.index
    ad = ds0.all_data()

    print '\n\n'
    print '----------------------------'
    print "[octree zoom_bbox_filter:] Calculating Center of Mass"


    gas_com_x = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,0])/np.sum(ad["gasdensity"])
    gas_com_y = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,1])/np.sum(ad["gasdensity"])
    gas_com_z = np.sum(ad["gasdensity"] * ad["gascoordinates"][:,2])/np.sum(ad["gasdensity"])


    com = [gas_com_x,gas_com_y,gas_com_z]

    print "[octree zoom_bbox_filter:] Center of Mass is at coordinates (kpc): ",com
    

    print "[octree zoom_bbox_filter:] Calculating Central Density Peak"
    
    density = ad["gasdensity"]
    wdens = np.where(density == np.max(density))[0]

    coordinates = ad["gascoordinates"]
    maxdens_coordinates = coordinates[wdens]
    

    if cfg.par.MANUAL_CENTERING == True:
        center = [cfg.model.x_cent,cfg.model.y_cent,cfg.model.z_cent]
    else:
        center = maxdens_coordinates[0]
        center = center.value
    
    print '[octree zoom_bbox_filter:] using center: ',center
    
    #DEBUG
    '''
    if cfg.par.COSMOFLAG==True:
        box_len = cfg.par.zoom_box_len/(1.+ds0.current_redshift)
    else:
        box_len = cfg.par.zoom_box_len
    '''
    box_len = cfg.par.zoom_box_len
    
    bbox_lim = box_len
    #bbox_lim = ds0.quan(box_len,'code_length')
    
    bbox1 = [[center[0]-bbox_lim,center[0]+bbox_lim],
            [center[1]-bbox_lim,center[1]+bbox_lim],
            [center[2]-bbox_lim,center[2]+bbox_lim]]
    print '[octree zoom] new zoomed bbox = ',bbox1
    

    ds1 = load(fname,unit_base=unit_base,bounding_box=bbox1,n_ref = cfg.par.n_ref,over_refine_factor=cfg.par.oref)
    ds1.periodicity = (False,False,False)

    #re-add the new powderday convention fields
    ds1 = gadget_field_add(None,unit_base,bbox1,ds=ds1)

    
    return ds1
