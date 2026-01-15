from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import SellerProfile
from apps.audit_engine.models import Audit, AuditStatus

User = get_user_model()

class AuditEngineTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='User'
        )
        self.seller_profile = SellerProfile.objects.get_or_create(user=self.user)[0]
        self.client = Client()
        self.client.login(email='test@example.com', password='testpassword123')

    def test_upload_reports_view_accessible(self):
        """Test accessing the manual upload page."""
        response = self.client.get(reverse('audit_engine:upload_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/upload_reports.html')

    def test_upload_invalid_file_extension(self):
        """Test uploading a file with wrong extension."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")
        response = self.client.post(reverse('audit_engine:upload_reports'), {'report_file': file})
        
        # Should redirect back with error
        self.assertEqual(response.status_code, 302)
        # Check messages (requires proper message checking in real tests, simplified here)
        
    def test_upload_valid_csv(self):
        """Test uploading a valid CSV file."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Simplified CSV content
        csv_content = b"sku,amount-total,order-id\nSKU123,-10.00,123-456-789"
        file = SimpleUploadedFile("report.csv", csv_content, content_type="text/csv")
        
        response = self.client.post(reverse('audit_engine:upload_reports'), {'report_file': file})
        
        # Check if audit created
        self.assertTrue(Audit.objects.filter(seller_profile=self.seller_profile).exists())
        audit = Audit.objects.first()
        self.assertEqual(audit.status, AuditStatus.COMPLETED)
        
        # Should redirect to results
        self.assertRedirects(response, reverse('audit_engine:audit_results'))

