import google.generativeai as genai

genai.configure(api_key="AIzaSyBnoG63eoDdi8sZqBqwS5Iag2BKj5hXs-I")

for m in genai.list_models():
    print(m.name)