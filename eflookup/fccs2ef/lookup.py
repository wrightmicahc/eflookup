"""eflookup.fccs2ef.lookup:

@todo:
 - Refactor/Reorganize all classes in this module.  They've become convoluted
   after various refactoring due to changing requirements.
 - Update SingleCoverTypeEfLookup.get to support specifying 'fuel_category' without specifying
   'phase', and to suport specifying 'species' without specifying either
   'phase' or 'fuel_category' (ex. to get all CO2 EFs associated with a
    specific FCCS fuelbed) (?)
"""

__author__      = "Joel Dubowy"

import abc
import logging

from .. import Phase
from .constants import CONSUME_FUEL_CATEGORY_TRANSLATIONS
from .mappers import (
    Fccs2CoverType,
    CoverType2EfGroup,
    CatPhase2EFGroup,
    EfGroup2Ef
)

__all__ = [
    'Fccs2Ef',
    'CoverType2Ef'
]

# RSC_KEYS = {
#     # Accept 'woody' and 'duff' to be explicitly selected
#     "woody": FuelCategory.WOODY,
#     "duff": FuelCategory.DUFF,
#     # Consume fuel categories with residual emissions
#     # TODO: check these!!!
#     # TODO: expect different keys???
#     "100-hr fuels": FuelCategory.WOODY,
#     "1000-hr fuels sound": FuelCategory.WOODY,
#     "1000-hr fuels rotten": FuelCategory.WOODY,
#     "10k+-hr fuels rotten": FuelCategory.WOODY,
#     "10k+-hr fuels sound": FuelCategory.WOODY,
#     "10000-hr fuels rotten": FuelCategory.WOODY,
#     "-hr fuels sound": FuelCategory.WOODY,
#     "stumps rotten": FuelCategory.WOODY,
#     "stumps lightered": FuelCategory.WOODY,
#     "duff lower": FuelCategory.DUFF,
#     "duff upper": FuelCategory.DUFF,
#     "basal accumulations": FuelCategory.DUFF,
#     "squirrel middens": FuelCategory.DUFF
# }

_categorie_tuples = CONSUME_FUEL_CATEGORY_TRANSLATIONS.values()
VALID_FUEL_CATEGORIES = [e[0] for e in _categorie_tuples]
VALID_FUEL_SUB_CATEGORIES = [e[1] for e in _categorie_tuples]


class BaseLookUp(object, metaclass=abc.ABCMeta):
    """Class for looking up emission factors for FCCS fuelbed types
    """

    def __init__(self, is_rx):
        """Constructor - reads FCCS-based emissions factors into dictionary
        for quick access.

        Args:
         - is_rx - set to True if a prescribed burn
        """
        self.is_rx = is_rx
        self.cat_phase_2_ef_group = CatPhase2EFGroup()
        self.ef_group_2_ef_loader = EfGroup2Ef()

        cover_type_id = getattr(self, 'cover_type_id', None)
        if not cover_type_id:
            # fccs_fuelbed_id should be a string, since it's not necessary
            # numeric but cast to string in case user specified it as an integer
            fccs_fuelbed_id = getattr(self, 'fccs_fuelbed_id')
            fccs_2_cover_type = Fccs2CoverType()
            cover_type_id = fccs_2_cover_type.get(str(fccs_fuelbed_id))
            if not cover_type_id:
                raise ValueError("Invalid FCCS Id".format(fccs_fuelbed_id))


        ef_set_type = 'rx' if is_rx else 'wf'
        cover_type_2_ef_group = CoverType2EfGroup()
        ef_groups = cover_type_2_ef_group.get(str(cover_type_id))
        if not ef_groups:
            raise ValueError("Invalid Covertype Id {}".format(cover_type_id))

        self.ef_group = ef_groups[ef_set_type]
        self.region = ef_groups['regrx' if is_rx else 'regwf']

        self.ef_set = self.ef_group_2_ef_loader.get(self.ef_group)
        self.ef_set_residual_woody = self.ef_group_2_ef_loader.get_woody_rsc()
        self.ef_set_residual_duff = self.ef_group_2_ef_loader.get_duff_rsc()


    def get(self, **kwargs):
        """Looks up and returns cover type specific emission factors

        Kwargs:
         - phase -- emissions factor set identifier ('flaming', 'smoldering',
            'residual')
         - fuel_category -- fuel category (ex. 'woody fuels', 'canopy', etc.)
            phase must also be defined
         - fuel_sub_category -- fuel sub-category (ex. '100-hr fuels',
            'stumps rotten', etc.); phase and fuel_category must also be
            defined
         - species -- chemical species; phase, fuel_category, and
            if fuel_sub_category must also be defined

        Notes:
         - fuel_category is effectively ignored for 'flaming' and 'smoldering'
            (since the same EFs are used accross all fuel categories)
         - returns None if any of the arguments are invalid.

        Examples:
        >>> lu = Fccs2Ef(52)
        >>> lu.get(phase='residual', fuel_category='canopy',
                fuel_sub_category='overstory', species='CO2')
        """
        if any([not kwargs.get(e) for e in ('phase', 'fuel_category', 'fuel_sub_category', 'species')]):
            raise LookupError("Specify phase, fuel_category, "
                "fuel_sub_category, and species")

        phase = kwargs.get('phase')
        fuel_category = kwargs.get('fuel_category')
        fuel_sub_category = kwargs.get('fuel_sub_category')
        species = kwargs.get('species')

        override_ef_group = -1
        if self.region:
            # Note: phase is nested under fuel category and sub-category in
            #   cat_phase_2_ef_group mapping data
            override_ef_group = self.cat_phase_2_ef_group.get(self.region,
                fuel_category, fuel_sub_category, phase, species, default=-1)

        def ef_or_none(ef_set, species):
            ef = ef_set.get(species)
            return float(ef) if ef else None

        try:
            if override_ef_group == None:
                # 'None' is specified in overrides, which means indicates
                # that there should be no emissions; so, return None
                return None

            elif override_ef_group == -1:
                # Not specified in overrides. Use base assignment
                if phase == Phase.RESIDUAL:
                    # TODO: return 0 unle it's woody or duff (based
                    #   on fuel catevory or sub category?) ???
                    if self.is_woody(fuel_category, fuel_sub_category):
                        return ef_or_none(self.ef_set_residual_woody, species)
                    elif self.is_duff(fuel_category, fuel_sub_category):
                        return ef_or_none(self.ef_set_residual_duff, species)
                    else:
                        return None
                else:
                    # flaming and smooldering use the same EF
                    # Note: if ef is not specified or empty string, use 0
                    return ef_or_none(self.ef_set, species)

            else:
                # return override value
                return ef_or_none(self.ef_group_2_ef_loader.get(override_ef_group), species)

        except KeyError:
             return None

    WOODY_CATEGORIES = ('canopy', 'woody fuels')
    WOODY_SUB_CATEGORIES = (
        "snags class 2",
        "snags class 3",
        "1000-hr fuels sound",
        "1000-hr fuels rotten",
        "10000-hr fuels sound",
        "10000-hr fuels rotten",
        "10k+-hr fuels sound",
        "10k+-hr fuels rotten",
        "stumps rotten",
        "stumps lightered"
    )
    def is_woody(self, fuel_category, fuel_sub_category):
        return (fuel_category in self.WOODY_CATEGORIES
            and fuel_sub_category in self.WOODY_SUB_CATEGORIES)

    def is_duff(self, fuel_category, fuel_sub_category):
        return fuel_category == 'ground fuels'

    def species(self, phase):
        # if phase not in self:
        #     return set()

        if phase == Phase.RESIDUAL:
            woody_keys = self.ef_set_residual_woody.keys()
            duff_keys = self.ef_set_residual_duff.keys()
            return set(woody_keys).union(duff_keys)
        else:
            return set(self.ef_set.keys())


class Fccs2Ef(BaseLookUp):

    def __init__(self, fccs_fuelbed_id, is_rx):
        self.fccs_fuelbed_id = str(fccs_fuelbed_id)
        super(Fccs2Ef, self).__init__(is_rx)


class CoverType2Ef(BaseLookUp):

    def __init__(self, cover_type_id, is_rx):
        self.cover_type_id = str(cover_type_id)
        super(CoverType2Ef, self).__init__(is_rx)
