'use client'
import { Button, Card, FileDropzone, Input, LabelLink, RichTextEditor, Select } from "src/components"
import PhotosOrganizer from "src/components/layout/Forms/PhotosOrganizer"
import style from './addKnowledge.module.scss'
import { useEffect, useState } from "react"
import { OptionType } from "src/components/layout/Forms/Select"
import { ArticlesApi } from "src/api"
import toast from "react-hot-toast"
import OutsideClickHandler from "react-outside-click-handler"

type AddKnowledgeProps = {
  setIsOpen: (e: boolean) => void;
  refreshKonwledge: () => void;
}

const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(error);
  });
};

const AddKnowledge = ({setIsOpen, refreshKonwledge}: AddKnowledgeProps) => {
    const [selectValue, setSelectValue] = useState<OptionType | null>(null);
    const [slug, setSlug] = useState<string>("")
    const [descriptions, setDescriptions] = useState<string>("")

    const [loading, setLoading] = useState<boolean>(false);

    const [images, setImages] = useState<File[]>([]);
    const [addImage, setAddImage] = useState<boolean>(false)
    const [categories, setCategories] = useState<Object[]>([]);

    const [isDisabledButton, setIsDisabledButton] = useState<boolean>(true);

    const getCategories = async() => {
    setLoading(true)
      try{
        const res = await ArticlesApi.getArticlesCategories();
        setLoading(false)
        setCategories(res.data.results)
      }catch(err){
        toast.error("Nie udalo sie pobrac kategorii")
        setLoading(false)
        setCategories([])
      }
    }
    useEffect(() => {
        getCategories();
    }, [])

  useEffect(() => {
    const isFormValid =
      slug.trim() !== '' &&
      descriptions.trim() !== '' &&
      selectValue !== null &&
      !loading;

    setIsDisabledButton(!isFormValid);
  }, [slug, descriptions, selectValue, loading]);

    const addKnowledge = async() => {
      if (isDisabledButton) {
        toast.error("Wypelnij wszystkie pola");
        return;
      }
      setLoading(true)
        try{
          const base64 = images.length > 0 ? await fileToBase64(images[0]) : null;
          const res = await ArticlesApi.postNewArticle({
            title: slug,
            ...(base64 && { image: base64 }),
            content: descriptions,
            categories: [selectValue?.value]
          });
          toast.success("Wiedza została dodana!");
          refreshKonwledge();
          setSlug("");
          setImages([]);
          setIsOpen(false);
        }catch (err: any) {
          console.error(err);
          toast.error("Nie udało się dodać posta");
        } finally {
          setLoading(false);
        }
    }


    return(
      <OutsideClickHandler onOutsideClick={() => setIsOpen(false)}>
        <Card className={style.container}>
          <header>
              <h2>Dodaj Wiedze</h2>
          </header>
          <div className={style.postCreate}>
              <Input 
                  label='Title' 
                  name='title'
                  placeholder={'Title...'}
                  value={slug}
                  onChangeText={setSlug}  
                  required
              />

              <Select
                label="Kategoria"
                options={categories.map((c: any) => ({
                  label: c.name,
                  value: c.id
                }))}
                value={selectValue}
                onChange={setSelectValue}
                isSearchable
                isClearable
                isLoading={loading}
              />
              
              <RichTextEditor
                  placeholder={'Napisz coś...'}
                  onChange={setDescriptions}
              />

            <LabelLink 
              label={!addImage ? "Dodaj zdjecie" : "Usun zdjecie"} 
              icon={!addImage ? 'plus' : 'x'} 
              onClick={() => setAddImage(prev => !prev)}
            />

              {addImage && (
                <div className={style.addImage}>
                  <h3>
                      Zaprezentuj <mark>zdjęcia</mark>
                  </h3>
    
                  <FileDropzone files={images} setFiles={setImages} />
                  <PhotosOrganizer photos={images} setPhotos={setImages} />
    
                  <span className={style.caption}>
                      Najlepiej na platformie będą wyglądać zdjęcia w formacie 4:3. Zdjęcia nie mogą przekraczać 5 MB. Dozwolone formaty to .png, .jpg, .jpeg
                  </span>
                </div>
              )}
          </div>
          <Button
              type="submit"
              label={loading ? "Publikuję..." : "Opublikuj"}
              disabled={isDisabledButton}
              onClick={addKnowledge}
          />
        </Card>
    </OutsideClickHandler>
    )
}

export default AddKnowledge;