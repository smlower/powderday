import numpy as np
import astropy.units as u
import yt
from yt import derived_field



#need - 
#1. PartType4_Metallicity (newstar metals)
#2. PartType4_coordinates
#3. Parttype4_StelarFormationTiome
#4. PartType0_Density
#5. PartType0_Metallicity
#6. Parttype0_Coordinates
#7. Parttype0_Smoothed_Density


def _starmetals(field,data):
    #return (data["PartType0","Density"]*data["PartType0","Metallicity"])
    return data[('Stars', 'Metals')]

yt.add_field(('starmetals'),function=_starmetals,units="code_metallicity",particle_type=True)

ds = yt.load('../tipsy/TipsyGalaxy/galaxy.00300')
ds.index
ad = ds.all_data()
print ad[("starmetals")]