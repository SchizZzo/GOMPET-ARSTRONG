'use client';

import React, {useEffect, useState} from 'react';
import classNames from 'classnames';
import { useTranslations } from 'next-intl';

import { IconNames } from 'src/assets/icons';
import { Button, Icon } from 'src/components';
import { IAnimal } from 'src/constants/types';

import style from './AnimalCard.module.scss';
import { usePathname, useRouter } from 'next/navigation';

import { useAppDispatch, useAppSelector, useAppStore } from 'src/lib/store/hooks';
import { addItemToFavorites, deleteItemFromFavorites } from '../../../bookmarks/slice';///
import OutsideClickHandler from 'react-outside-click-handler';
import toast from 'react-hot-toast';
import { Routes } from 'src/constants/routes';
import SettingsButton from 'src/components/layout/Settings';
import { ArticlesApi } from 'src/api';
import { useSession } from 'next-auth/react';

const genderIconNames: { [key: string]: IconNames } = {
  male: 'genderMale',
  female: 'genderFemale'
};

type AnimalCardProps = {
  className?: string;
  animal: IAnimal;
  isSettingsOpen?: boolean;
  setOpenedCardId?: (id: string | null) => void;
  onToggleSettings?: () => void;
  onDelete?: (id: number) => void;
  onReactionDelete?: (id: number) => void;
};

const AnimalCard = ({ className, animal, setOpenedCardId, onDelete, onReactionDelete }: AnimalCardProps) => {

  const dispatch = useAppDispatch();
  const pathname = usePathname();
  const session = useSession();
  // const favorites = useAppSelector((state) => state.bookmarks.favorites);
  // const isFavorite = favorites.some((fav) => fav.id === animal.id);
  // const [isLiked, setIsLiked] = useState<boolean>();
  // const [isLoading, setIsLoading] = useState(false);

  // const toggleReaction = async () => {
  //   if (!session) {
  //     toast.error('Musisz być zalogowany');
  //     return;
  //   }

  //   if (isLoading) return;

  //   setIsLoading(true);
  //   setIsLiked(prev => !prev); // optimistic update

  //   try {
  //     if (isLiked) {
  //       await ArticlesApi.deleteReaction(animal.id);
  //     } else {
  //       await ArticlesApi.AddNewReaction({
  //         reactable_type: 'animals.animal',
  //         reactable_id: animal.id,
  //         reaction_type: 'LIKE',
  //       });
  //     }
  //   } catch (err) {
  //     setIsLiked(prev => !prev); // rollback
  //     toast.error('Nie udało się zapisać reakcji');
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };




  const [reactionId, setReactionId] = useState<number>(0); // 0 = brak reakcji
  // const [likeCount, setLikeCount] = useState<number>();

  const myId = session.data?.user?.id;

  // useEffect(() => {
  //   setLikeCount(reactionsCount);
  // }, [reactionsCount])

  // ✅ sprawdzamy czy user polubił post
  useEffect(() => {
    const checkReaction = async () => {
      try {
        const res = await ArticlesApi.verifyReactions("animals.animal", animal.id);
        setReactionId(res?.data?.reaction_id ?? 0);
        console.log("verifyReactions res:", res);
      } catch (err) {
        console.error("Błąd przy sprawdzaniu reakcji:", err);
      }
    };

    if (session.status === "authenticated") {
      checkReaction();
    }
  }, [animal.id, session.status]);

  // ✅ obsługa polubienia
  const handleReaction = async () => {
    const isLoggedInUser = session.status === 'authenticated' && !!myId;
    if (!isLoggedInUser) {
      toast.error('Musisz być zalogowany, aby polubić post.');
      return;
    }

    if (reactionId === 0) {
      // ➕ dodanie reakcji
      try {
        const res = await ArticlesApi.AddNewReaction({
          reaction_type: "LIKE",
          reactable_type: "animals.animal", // upewnij się że backend oczekuje stringa a nie 26
          reactable_id: animal.id,
        });

        if (res?.status === 201) {
          setReactionId(res.data.id);
          // setLikeCount(prev => prev + 1);
        }

        console.log("Add reaction res:", res);
      } catch (err) {
        console.error("Błąd przy dodawaniu reakcji:", err);
      }
    } else {
      // ➖ usunięcie reakcji
      try {
        const res = await ArticlesApi.deleteReaction(reactionId);

        if (res?.status === 200 || res?.status === 204) {
          setReactionId(0);
          onReactionDelete(animal.id);
          // setLikeCount(prev => Math.max(prev - 1, 0));
        }

        console.log("Delete reaction res:", res);
      } catch (err) {
        console.error("Błąd przy usuwaniu reakcji:", err);
      }
    }
  };








  const t = useTranslations('pages.animals');
  const {push} = useRouter();

  const cardClasses = classNames(style.card, className);
  const cardStyles = {
    backgroundImage: `url(${animal.image})`,
  };

  // const toggleFavorite = () => {
  //   const isFav = favorites.some((fav) => fav.id === animal.id);
  //   if (isFav) {
  //     dispatch(deleteItemFromFavorites(animal));
  //   } else {
  //     dispatch(addItemToFavorites(animal));
  //   }
  // };

  const handleUpdateClick = () => {
    push(Routes.EDIT(animal.id))
    setOpenedCardId?.(null);
  };

  return (
    <div className={cardClasses} style={cardStyles}>
      <div className={style.gradient}></div>
      <div className={style.content}>
        <div className={style.top}>
          <div className={style.about}>
            <h2 className={classNames(style.badge, style.title)}>{animal.name}</h2>
            {/* {animal.age && ( */}
              <div className={classNames(style.badge, style.age)}>{animal.age >= 1 ? (`${animal.age}+`) : '< 1 rok'}</div>
            {/* )} */}
            {animal.characteristicBoard.find(item => item.bool === true) && (
              <div className={classNames(style.badge, style.characteristics)}>
                {/* {t(`characteristics.${animal.species}.${animal.characteristicBoard[0].title}`)} */}
                {(() => {
                  const firstTrue = animal.characteristicBoard.find(item => item.bool === true);
                  return firstTrue ? firstTrue.title : null;
                })()}
              </div>
            )}
          </div>
          <button className={classNames(style.addBookmark, {
            [style['addBookmark--active']]: reactionId !== 0, //animal?.liked-by == Number(myId)
          })} onClick={() => handleReaction()}>
            <Icon name='heart' />
          </button>

          {pathname == '/my-animals' && (
            <div onClick={(e) => e.stopPropagation()} className={style.addBookmark}>
              <SettingsButton
                authId={animal.owner}
                onEdit={handleUpdateClick}
                onDelete={() => {
                  onDelete?.(animal.id);
                  setOpenedCardId?.(null); 
              }} 
              />
            </div>

          )}

        </div>

        <div className={style.hoverContent} >
          <div className={style.data}>
            <div className={classNames(style.badge, style.gender)}>
              <span>Płeć:  {t(`gender.${(animal.gender).toLowerCase()}`)}</span>
              <Icon name={genderIconNames[animal.gender]} />
            </div>
            <div className={classNames(style.badge, style.size)}>Wielkość: {t(`size.${animal.size.toLowerCase()}`)}</div>
            <div className={classNames(style.badge, style.ageText)}>Wiek: Dorosły</div>
          </div>
          <Button 
            className={style.buttonCard} 
            label="Poznaj szczegóły" 
            onClick={() => push(`/animals/${animal.id}`)} 
          />
        </div>

        <div className={style.bottom}>
          <div className={style.location}>
            <Icon name='mapPin' />
            <span>{animal.city}</span>
          </div>
        </div>
      </div>
    </div>
    
  );
};

export default AnimalCard;
