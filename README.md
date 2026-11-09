# django-demos
Demonstration Django apps

<img src="https://wiest.world/images/file_demo_index_page.jpg">
<img src="https://wiest.world/images/file_demo_details_page.jpg">

## Host-site navigation

The shared demo header includes an optional
`dwiest-django-demos/components/site_navigation.html` template before the
application switcher. Its default content is empty. Host projects can override
that template in their project template directory to provide navigation to
other site areas, without copying or replacing the demo application menu.
Keep project template directories ahead of app templates in Django's loader
order. The hook does not change authentication or application routes.
