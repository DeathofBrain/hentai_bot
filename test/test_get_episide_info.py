from jmcomic import *

client = JmOption.default().new_jm_client()

# 单本多章节本子：JM1027519 NTR魔法使的冒险 [纟杉柾宏、まじかり、まくわうに]寝取り魔法使いの冒险
album: JmAlbumDetail = client.get_album_detail('1027519')

if __name__ == "__main__":
    print(f"本子标题: {album.title}")
    '''本子标题: NTR魔法使的冒险 [纟杉柾宏、まじかり、まくわうに]寝取り魔法使いの冒险
    本子标题列表: [('1027519', '1', ''), 
    ('1031235', '2', ''), ('1035231', '3', ''), ('1039976', '4', ''), ('1045297', '5', ''), 
    ('1050146', '6', '第一卷附录小说'), ('1054768', '7', '6'), …]'''

    print(f"本子标题列表: {album.episode_list}")
    print(f"本子章节数: {len(album.episode_list)}")
    print(f"本子封面: {album.is_album()}")
