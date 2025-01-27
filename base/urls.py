from django.shortcuts import render
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),

    path('admin-panel', views.adminPanel, name="admin-panel"),

    path('logout/', views.logout_user, name='logout'),
    path('profile/<str:userID>', views.profile, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('home/', views.home, name="home"),
    path('notifications/', views.getNotifications, name="notifications"),
    path('create-complaint/', views.createComplaint, name="create-complaint"),
    path('view-complaint/<str:complaintID>', views.viewComplaint, name="view-complaint"),
    path('delete-complaint/<str:complaintID>', views.deleteComplaint, name="delete-complaint"),
    path('mark-as-resolved/<str:complaintID>', views.markAsResolved, name="mark-resolved"),
    path('reopen/<str:complaintID>', views.reOpen, name="re-open"),
    path('admin-category/', views.addCategories, name="category-update"),
    path('admin-disable-category/<str:categoryID>', views.disableCategory, name="disable-category"),
    path('admin-enable-category/<str:categoryID>', views.enableCategory, name="enable-category"),
    path('badges/', views.addBadges, name='badges-update'),
    path('admin-edit-moderators/', views.editModerators, name="moderators-update"),
    path('disable-user/', views.disableUser, name='disable-user'),
    path('disabled-user-message/', views.disabledUserMessage, name='disabled_user_message'),
    path('enable-user/<str:userID>', views.enableUser, name='enable-user'),
    path('admin-remove-moderator/<str:userID>', views.removeModerator, name="moderator-remove"),
    path('approve-complaints/', views.approveComplaints, name="approve-complaints"),
    path('approve-complaint/<str:complaintID>', views.approveComplaint, name="approve-complaint"),
    path('force-close-complaint/<str:complaintID>', views.forceCloseComplaint, name="force-close-complaint"),
    path('auto-close/', views.autoClose, name="auto-close"),
    path('about-us/', views.aboutUs, name='about-us'),
    path('terms-and-conditions/', views.tnc, name='tnc'),
    path('privacy-policy/', views.privacyPolicy, name='privacy-policy'),
    path('restricted-content/', views.restrictedContent, name='restricted_content'),
    path('restricted-text/', views.restrictedText, name='restricted_text'),
    path('set-autoclose/', views.setAutoCloseTimePeriod, name='set_autoclose'),
    path('error/', views.error, name='error'),
    path('invalid-file-format/', views.invalidFileFormat, name='invalid_file_format'),
    path('file-size-too-large', views.fileSizeTooLarge, name='file_too_large'),

    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('impact/', views.impact, name='impact'),
    path('success-message/', views.complaintPostedSuccess, name='complaint-posted-success'),
    path('complaint-already-approved/', views.complaintAlreadyApproved, name='complaint-already-approved'),
]

