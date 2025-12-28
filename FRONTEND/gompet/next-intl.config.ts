import type { NextIntlConfig } from 'next-intl';

import { locales } from './src/navigation';

const config: NextIntlConfig = {
  locales,
  defaultLocale: 'pl'
};

export default config;
