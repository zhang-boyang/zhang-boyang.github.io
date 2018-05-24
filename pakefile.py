import os
import sys
import argparse
import time

tilte_template = "---\nlayout: post\ntitle: \"%s\"\n---\n"
path = "./_posts/"
def create_post_file(post_name):
    if not os.path.isdir(path):
        os.mkdir(path)
    str_time = time.strftime('%Y-%m-%d',time.localtime(time.time()))
    file_name = path + str_time + "-" + post_name.replace("_", "-") + ".md"
    post_title = post_name.replace("_", " ")
    with open(file_name, "w+") as fout:
        fout.write(tilte_template % (post_title))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--post_name', type=str, help='Post file path')
    args = parser.parse_args()
    post_name = args.post_name
    
    create_post_file(post_name)
    
    os.system('bundle exec jekyll serve')

if __name__ == "__main__":
    main()
    
