import os



#获取工程的根目录
def get_project_root()->str:
    current_file=os.path.abspath(__file__)    #当前文件的绝对路径

    current_dir=current_dir=os.path.dirname(current_file)             #先获取文件所在的文件夹

    project_root=os.path.dirname(current_dir)    #获取工程的根目录

    return project_root


#传递相对路径，得到绝对路径
def get_abs_path(relative_path:str)->str:
    project_root=get_project_root()
    return os.path.join(project_root,relative_path)




