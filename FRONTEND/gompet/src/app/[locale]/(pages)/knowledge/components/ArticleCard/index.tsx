import React from 'react';
import classNames from 'classnames';

import { Button, Icon } from 'src/components';
import { Routes } from 'src/constants/routes';
import { IArticle } from 'src/constants/types';
import { Link } from 'src/navigation';

import style from './ArticleCard.module.scss';
import DescriptionTranslate from 'src/components/layout/Forms/RichTextTranslation';
import SettingsButton from 'src/components/layout/Settings';
import { useSession } from 'next-auth/react';
import { ArticlesApi } from 'src/api';
import toast from 'react-hot-toast';

type ArticleCardProps = {
  className?: string;
  article: IArticle;
  setKnowledge: () => void;
};

const KnowledgeCard = ({ article, className, setKnowledge }: ArticleCardProps) => {
  const { id, title, content, image = null, created_at, slug } = article;
  console.log(article);
  const session = useSession();
  const myId = session.data?.user.id

  const deleteKnowledge = async() => {
    try{
      const res = await ArticlesApi.deleteArticlePage(slug);
      console.log(res);
      toast.success("Post zostal usuniaty")
      setKnowledge((prev) => prev.filter(p => p.slug !== slug));
    }catch(err){
      toast.error("Nie udalo sie usunac posta")
      console.log(err)
    }
  }

  return (
    <article className={classNames(style.article, className)}>
      <div className={style.modalSettings}>
        <SettingsButton 
          authId={myId} 
          onDelete={deleteKnowledge}
        />
      </div>

      <Link
        className={style.cover}
        href={Routes.BLOG_ARTICLE(slug)}
      >
        {image ? (
          <img
            src={image}
            alt={title}
          />
        ) : (
          <Icon
            className={style.placeholderIcon}
            name='camera'
          />
        )}
      </Link>

      <div className={style.body}>
        <Link href={Routes.BLOG_ARTICLE(slug)}>
          <h2 className={style.title}>{title}</h2>
        </Link>
        {/* <p className={style.content}>{DescriptionTranslate(content)}</p> */}
        <div className={style.content}>
          <DescriptionTranslate text={content}/>
        </div>
        <Button
          label={'Przeczytaj artykuł'}
          href={Routes.BLOG_ARTICLE(slug)}
        />
      </div>
    </article>
  );
};

export default KnowledgeCard;
