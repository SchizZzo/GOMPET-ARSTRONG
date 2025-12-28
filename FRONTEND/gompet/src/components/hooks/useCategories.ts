'use client';

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';

export type Category = {
  id: number;
  label: string;
};

const useCategories = () => {
  const t = useTranslations('common');

  const categories: Category[] = useMemo(
    () => [
      { id: 1, label: t('categories.breeding') },
      { id: 2, label: t('categories.walking') }
    ],
    [t]
  );

  return { categories };
};

export default useCategories;
