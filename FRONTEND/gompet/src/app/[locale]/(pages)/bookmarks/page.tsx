'use client';

import React, { useEffect, useState } from 'react';
import style from './Bookmarks.module.scss';
import classNames from 'classnames';
import { List } from 'src/components';
import { useTranslations } from 'next-intl';
import { IAnimal } from 'src/constants/types';
import { AnimalsApi } from 'src/api';
import { useSession } from 'next-auth/react';
import AnimalCard from '../animals/components/AnimalCard';

const Bookmarks = () => {
  const t = useTranslations('pages.animals');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [animals, setAnimals] = useState<IAnimal[]>([]);

  const session = useSession()
  const myId = session.data?.user.id;

  const postReaction = async () => {
    setIsLoading(true);
    try {
      const res = await AnimalsApi.getUserBookmarks(Number(myId));
      setAnimals(res.data?.results)
    } catch {
      setAnimals([])
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    postReaction();
  }, [])

  const onReactionDelete = (deletedAnimal: number) => {
    setAnimals(animals.filter(animal => animal.id !== deletedAnimal));
  }
  

  return (
    <div className={style.bookmarksWrapper}>
      <List
        isLoading={isLoading}
        className={classNames(style.list)}
      >
          {animals.map((animal: any) => (
            <AnimalCard key={animal.id} animal={animal} onReactionDelete={onReactionDelete} />
          ))}
      </List>
    </div>
  );
};

export default Bookmarks;