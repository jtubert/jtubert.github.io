---
layout: default
title:  "jtubert.com"
date:   2025-06-08 11:16:09 -0400
---

{% comment %}
  {% assign story = site.data.stories[24] %}
  
  "https://fpoimg.com/500x380?text=Preview&bg_color=e6e6e6&text_color=8F8F8F"
{% endcomment %}
 

 
{% for story in site.data.stories %}

  {% assign aa = "hgajlbldbp" %}

  {% if story.type == "video" %}
    {% assign aa = "hgajlbldbp" %}
  {% else %}
    {% assign aa = "5000ms" %}
  {% endif %}

  {% include templates/{{ story.template }}.html
    id=story.id
    category=story.category 
    title=story.title 
    date=story.date 
    link=story.link
    asset=story.asset
    type=story.type
    autoAdvance=aa
    template=story.template
    poster=story.poster
  %}
{% endfor %}
