from django.urls import path

from . import views

urlpatterns = [
    path("", views.root_redirect, name="home"),
    path("dang-nhap/", views.login_view, name="login"),
    path("dang-xuat/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path('thi-sinh/import/', views.import_students, name='import_students'),
    path('phien-thi/tao/', views.create_session, name='create_session'),
    path('phien-thi/<int:pk>/quet/', views.assign_scan, name='assign_scan'),
    path('phien-thi/<int:pk>/bien-ban.pdf', views.bien_ban_thi_pdf, name='bien_ban_thi_pdf'),
    path('qr/dot-in/', views.qr_batches, name='qr_batches'),
    path('qr/dot-in/<int:pk>/in.pdf', views.qr_batch_pdf, name='qr_batch_pdf'),
    path('quan-tri/users/', views.manage_users, name='manage_users'),
    path('cham-diem/', views.score_list, name='score_list'),
    path("cham-diem/bang-diem-lop/", views.bang_diem_lop, name="bang_diem_lop"),
    path("cham-diem/bang-diem-lop/pdf/", views.bang_diem_lop_pdf, name="bang_diem_lop_pdf"),
    path('cham-diem/<int:pk>/', views.score_detail, name='score_detail'),
    path('lich-su/', views.logs, name='logs'),
    path('phien-thi/<int:pk>/logs/', views.session_logs, name='session_logs'),
    path('qr/dot-in/<int:pk>/excel/', views.qr_batch_excel, name='qr_batch_excel'),
    path('cham-diem/gk1/', views.cham_diem_gk1, name='cham_diem_gk1'),
    path('cham-diem/gk2/', views.cham_diem_gk2, name='cham_diem_gk2'),
    path('cham-diem/doi-chieu/<int:pk>/', views.cham_diem_doi_chieu, name='cham_diem_doi_chieu'),
    path('cham-diem/thong-nhat/<int:pk>/', views.cham_diem_thong_nhat, name='cham_diem_thong_nhat'),   
    path('cham-diem/bang-diem-lop/', views.bang_diem_lop, name='bang_diem_lop'),
]
