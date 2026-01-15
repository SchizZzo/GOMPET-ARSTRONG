import axios from 'axios';
import { IAnimal, IComment } from 'src/constants/types';
import style from './AnimalProfile.module.scss';
import { AnimalsApi } from 'src/api';
import TabView from '../components/AnimalProfile/TabView';

const getAnimalData = async (id: number): Promise<IAnimal | undefined> => {
  try {
    const animalProfileRes = await AnimalsApi.getAnimalProfile(id);
    return animalProfileRes.data
  } catch (error) {
    console.error('Error fetching animal:', error);
    return undefined;
  }
};

const getAnimalFamilyTree = async (id: number): Promise<IAnimal | undefined> => {
  try {
    const animalFamilyTreeRes = await AnimalsApi.getAnimalFamilyTree(id); 
    return animalFamilyTreeRes.data
  } catch (error) {
    console.error('Error fetching animal:', error);
    return undefined;
  }
};

// const getAnimalPosts = async (id: number): Promise<IPost | undefined> => {
//   try{
//     const animalPosts = await PostsApi.getAnimalPosts(id);
//     return animalPosts.results
//   }catch(error){
//     throw error
//   }
// }

const getCommentData = async (id: number): Promise<IComment[]> => {
  try {
    const animalCommentsRes = await AnimalsApi.getAnimalComments(id);
    return animalCommentsRes.data || [];
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return [];
    }
    console.error('Error fetching animal comments:', error);
    return [];
  }
};

export const generateMetadata = async ({
  params
}: {
  params: Promise<{ id: string }>;
}) => {
  const { id } = await params;
  const animalData = await getAnimalData(Number(id));
  
  return {
    title: animalData?.name || 'Unknown Animal',
    description: animalData?.species || 'Animal details',
    openGraph: {
      images: animalData?.image ? [animalData.image] : [],
    },
  };
};

const AnimalDetailPage = async ({ params }: { params: Promise<{ id: string }> }) => {
  const { id } = await params;
  const animal = await getAnimalData(Number(id));
  const familyTree = await getAnimalFamilyTree(Number(id))
  const comments = await getCommentData(Number(id));
  // const posts = await getAnimalPosts(Number(params.id))

  if (!animal) {
    return <div className={style.notFound}>Animal not found</div>;
  }
//posts={posts}
  return (
    <div className={style.mainContainer}>
      <div className={style.innerContainer}>
        {/* <AnimalProfile animal={animal} comment={comment} posts={posts} familyTree={familyTree} />  */}
        <TabView animal={animal} comments={comments}  familyTree={familyTree} /> 
      </div>
    </div>
  );
};

export default AnimalDetailPage;
