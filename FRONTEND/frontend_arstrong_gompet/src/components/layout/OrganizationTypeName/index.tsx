import React from 'react';
import { useTranslations } from 'next-intl';

import { Icon } from 'components';

import { IconNames } from 'src/assets/icons';
import { OrganizationType } from 'src/constants/types';

import style from './OrganizationTypeName.module.scss';

type OrganizationTypeNameProps = {
  type?: OrganizationType | string | null;
};

const OrganizationTypeName = ({ type }: OrganizationTypeNameProps) => {
  const t = useTranslations();

  const organizationIcon: { [key: string]: IconNames } = {
    [OrganizationType.ANIMAL_SHELTER]: 'homeHeart',
    [OrganizationType.FUND]: 'shieldHeart',
    [OrganizationType.BREEDING]: 'buildingCottage',
    SHELTER: 'homeHeart',
    FUND: 'shieldHeart',
    BREEDER: 'buildingCottage'
  };

  const organizationLabels: { [key: string]: string } = {
    [OrganizationType.ANIMAL_SHELTER]: 'SHELTER',
    [OrganizationType.FUND]: 'FUND',
    [OrganizationType.BREEDING]: 'BREEDER',
    SHELTER: 'SHELTER',
    FUND: 'FUND',
    BREEDER: 'BREEDER'
  };

  const resolvedType = type && organizationLabels[type] ? type : null;
  const iconName = resolvedType ? organizationIcon[resolvedType] : undefined;
  const label = resolvedType
    ? t(`common.organization.${organizationLabels[resolvedType]}`)
    : t('common.organization.UNKNOWN');

  return (
    <div className={style.type}>
      {iconName && (
        <Icon
          name={iconName}
          gray
        />
      )}
      <span>{label}</span>
    </div>
  );
};

export default OrganizationTypeName;
