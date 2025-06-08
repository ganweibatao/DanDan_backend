from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LearningPlanViewSet, LearningUnitViewSet, UnitReviewViewSet

router = DefaultRouter()
router.register('plans', LearningPlanViewSet, basename='learningplan')
router.register('units', LearningUnitViewSet, basename='learningunit')
router.register('reviews', UnitReviewViewSet, basename='unitreview')

urlpatterns = [
    path('', include(router.urls)),
] 