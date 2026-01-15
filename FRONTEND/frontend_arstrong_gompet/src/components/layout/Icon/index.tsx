import classNames from 'classnames';
import type { ComponentType, ImgHTMLAttributes, SVGProps } from 'react';

import { IconNames, Icons } from 'src/assets/icons';
import { Link } from 'src/navigation';

import style from './Icon.module.scss';

interface IconProps extends Partial<HTMLAnchorElement> {
  name: IconNames;
  href?: string;
  hrefOutside?: string;
  small?: boolean;
  svgProps?: SVGProps<SVGSVGElement>;
  gray?: boolean;
  dark?: boolean;
  white?: boolean;
  colored?: boolean;
  noPointerEvents?: boolean;
  currentColor?: boolean;
  onClick?: () => void;
}

const Icon = (props: IconProps) => {
  const {
    name,
    className,
    href,
    hrefOutside,
    onClick,
    small,
    svgProps,
    gray,
    dark,
    white,
    colored,
    noPointerEvents,
    currentColor = false
  } = props;

  const iconProps = {
    className: classNames(style.icon, className, {
      [style.small]: small,
      [style.gray]: gray,
      [style.dark]: dark,
      [style.white]: white,
      [style.colored]: colored,
      [style.noPointerEvents]: noPointerEvents,
      [style.currentColor]: currentColor
    }),
    ...svgProps
  };

  const IconComponent = Icons[name] as
    | ComponentType<SVGProps<SVGSVGElement>>
    | {
        src?: string;
        default?: ComponentType<SVGProps<SVGSVGElement>> | string;
      }
    | string
    | undefined;

  if (!IconComponent) return null;

  const renderIcon = () => {
    const { className: iconClassName } = iconProps;
    const imgProps: ImgHTMLAttributes<HTMLImageElement> = {
      className: iconClassName,
      alt: '',
      width: svgProps?.width,
      height: svgProps?.height
    };

    if (typeof IconComponent === 'function') {
      return <IconComponent {...iconProps} />;
    }

    if (typeof IconComponent === 'string') {
      return (
        <img
          {...imgProps}
          src={IconComponent}
        />
      );
    }

    if (typeof IconComponent === 'object' && IconComponent !== null) {
      if (typeof IconComponent.default === 'function') {
        const DefaultComponent = IconComponent.default;
        return <DefaultComponent {...iconProps} />;
      }

      const iconSrc = IconComponent.src ?? IconComponent.default;
      if (typeof iconSrc === 'string') {
        return (
          <img
            {...imgProps}
            src={iconSrc}
          />
        );
      }
    }

    return null;
  };

  if (hrefOutside) {
    return (
      <a
        href={href}
        className={style.link}
        target='_blank'
        rel='noreferrer'
      >
        {renderIcon()}
      </a>
    );
  }

  if (href) {
    return (
      <Link
        href={href}
        className={style.link}
      >
        {renderIcon()}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button
        className={style.button}
        onClick={onClick}
      >
        {renderIcon()}
      </button>
    );
  }

  return renderIcon();
};

export default Icon;
