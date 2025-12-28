'use client'
import DescriptionTranslate from "src/components/layout/Forms/RichTextTranslation";
import { IArticle } from "src/constants/types";
import style from './BlogArticlePage.module.scss'

const KnowledgePage = ({ data }: { data: IArticle }) => {
    console.log('data:', data);
  
    return (
      <div className={style.container}>
        <h1>{data.title}</h1>
        {/* <p>{data.content}</p> */}
        <DescriptionTranslate text={data.content} />
      </div>
    );
  };

export default KnowledgePage;