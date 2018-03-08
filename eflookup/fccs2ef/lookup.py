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

from ..constants import Phase, CONSUME_FUEL_CATEGORY_TRANSLATIONS
from .load import (
    EFSetTypes,
    Fccs2CoverTypeLoader,
    CoverType2EfGroupLoader,
    CatPhase2EFGroupLoader,
    EfGroup2EfLoader
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

_categorie_tuples = [
    e.split(':') for e in CONSUME_FUEL_CATEGORY_TRANSLATIONS.values()
]
VALID_FUEL_CATEGORIES = [e[0] for e in _categorie_tuples]
VALID_FUEL_SUB_CATEGORIES = [e[1] for e in _categorie_tuples]

class SingleCoverTypeEfLookup(object):
    """Lookup class containing EFs for a single FCCS or cover type id

    Objects of this class are passed to emissions
    """

    def __init__(self, cover_type_id, is_rx, cover_type_2_ef_group,
            cat_phase_2_ef_group, ef_group_2_ef_loader):
        """Constructor

        Args
         - cover_type_id
         - is_rx -- wether or not it's a prescribed burn
         - cover_type_2_ef_group
         - cat_phase_2_ef_group
         - ef_group_2_ef_loader
        """

        ef_set_type = EFSetTypes.FLAME_SMOLD_RX if is_rx else EFSetTypes.FLAME_SMOLD_WF
        ef_groups = cover_type_2_ef_group[str(cover_type_id)]

        self.ef_group = ef_groups[ef_set_type]
        self.region = ef_groups[EFSetTypes.REGIONAL_RX]

        self.ef_set = self._ef_group_2_ef_loader.get(self.ef_group)
        self.ef_set_residual_woody = ef_group_2_ef_loader.get_woody_rsc()
        self.ef_set_residual_duff = ef_group_2_ef_loader.get_duff_rsc()

        self.cat_phase_2_ef_group = cat_phase_2_ef_group

    def get(self, phase, fuel_category, fuel_sub_category, species):
        """Looks up and returns cover type specific emission factors

        Lookup Keys:
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
        >>> lu = LookUp()
        >>> lu.get(phase='residual', fuel_category='canopy',
                fuel_sub_category='overstory', species='CO2')
        """
        if any([not e for e in (phase, fuel_category, fuel_sub_category, species)]):
            raise LookupError("Specify phase, fuel_category, "
                "fuel_sub_category, and species")

        override_ef_group = self.cat_phase_2_ef_group.get(phase,
            fuel_category, fuel_sub_category, species, default=-1)

        try:
            if override_ef_group == None:
                # 'None' is specified in overrides, which means indicates
                # that there should be no emissions; so, return None
                return None

            elif override_ef_groupef_group == -1:
                # Not specified in overrides. Use base assignment
                if phase == Phase.RESIDUAL:
                    # TODO: return 0 unle it's woody or duff (based
                    #   on fuel catevory or sub category?) ???
                    if self.is_woody(fuel_category, fuel_sub_category):
                        return self.ef_set_residual_woody[species]
                    elif self.is_duff(fuel_category, fuel_sub_category):
                        return self.ef_set_residual_duff[species]
                    else:
                        return None
                else:
                    # flaming and smooldering use the saem EF
                    self.ef_set[species]

            else:
                # return override value
                return self.ef_groups[override_ef_group][species]

        except KeyError:
             return None

    def is_woody(self, fuel_category, fuel_sub_category):
        # TODO: is this correct?
        return fuel_category == 'woody fuels'

    def is_duff(self, fuel_category, fuel_sub_category):
        # TODO: is this correct?
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

class BaseLookUp(object, metaclass=abc.ABCMeta):
    """Class for looking up emission factors for FCCS fuelbed types
    """

    def __init__(self, is_rx, **options):
        """Constructor - reads FCCS-based emissions factors into dictionary
        for quick access.

        Args:
         - is_rx - set to True if a prescribed burn

        Options:
         - fccs_2_cover_type_file --
         - cover_type_2_ef_group_file --
         - cat_phase_2_ef_group_file --
         - ef_group_2_ef_file --
        """
        self.is_rx = is_rx
        self._fccs_2_cover_type = Fccs2CoverTypeLoader(
            file_name=options.get('fccs_2_cover_type_file')).get()
        self._cover_type_2_ef_group = CoverType2EfGroupLoader(
            file_name=options.get('cover_type_2_ef_group_file')).get()
        self._cat_phase_2_ef_group = CatPhase2EFGroupLoader(
            file_name=options.get('cat_phase_2_ef_group_file')).get()
        self._ef_group_2_ef_loader = EfGroup2EfLoader(
            file_name=options.get('ef_group_2_ef_file'))
        self.cover_type_look_ups = {}

    def get(self, **keys):
        """Looks up and returns emissions factor info for the fccs fuelbed type
        or cover type.

        Delegates to SingleCoverTypeEfLookup, instantiated and memoized per
        distinct cover type, to do most of the work.

        Lookup Keys:

        phase, fuel_category, fuel_sub_category, and species kwargs
        are all required. They are specified as **keys to conform to
        the eflookup..lookup.BasicEFLookup interface

        Notes:
         - returns None if any of the arguments are invalid.

        Examples:
        >>> lu = Fccs2Ef(52)
        >>> lu.get(phase='residual', fuel_category='woody fuels',
                fuel_sub_category='1-hr fuels' species='CO2')
        """
        try:
            cover_type_id = getattr(self, 'cover_type_id', None)
            if not cover_type_id:
                # fccs_fuelbed_id should be a string, since it's not necessary
                # numeric but cast to string in case user specified it as an integer
                fccs_fuelbed_id = getattr(self, 'fccs_fuelbed_id')
                cover_type_id = self._fccs_2_cover_type[str(fccs_fuelbed_id)]


            if cover_type_id not in self.cover_type_look_ups:
                self.cover_type_look_ups[cover_type_id] = SingleCoverTypeEfLookup(
                    cover_type_id,
                    self.is_rx,
                    self._cover_type_2_ef_group,
                    self._cat_phase_2_ef_group,
                    self._ef_group_2_ef_loader)

        except KeyError:
            return None

        return self.cover_type_look_ups[cover_type_id].get(**keys)


class Fccs2Ef(BaseLookUp):

    def __init__(self, fccs_fuelbed_id, is_rx, **options):
        self.fccs_fuelbed_id = fccs_fuelbed_id
        super(Fccs2Ef, self).__init__(is_rx, **options)


class CoverType2Ef(BaseLookUp):

    def __init__(self, cover_type_id, is_rx, **options):
        self.cover_type_id = cover_type_id
        super(CoverType2Ef, self).__init__(is_rx, **options)
